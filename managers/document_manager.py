import streamlit as st
import io
import PyPDF2
import uuid
import pandas as pd
import requests
import time
import concurrent.futures
from pathlib import Path
from stqdm import stqdm

from .pinecone_manager import PineconeManager
from .session_manager import SessionManager
from .llm_manager import LLMManger
from .cost_manager import CostManager


class DocumentManager:
    @staticmethod
    def load_pdf(bytes_data, tag, name, desc):
        p = io.BytesIO(bytes_data)
        reader = PyPDF2.PdfReader(p)
        data = []

        for i in stqdm(range(len(reader.pages)), desc=desc):
            content = reader.pages[i].extract_text()
            clean_content = content.encode('utf-8', 'replace').decode('utf-8')

            if len(content) < 10:
                continue

            data.append({
                "tag": tag,
                "name": name,
                "page": i + 1,
                "content": clean_content,
            })

        return data

    @staticmethod
    def get_document_titles_by_tag(tag):
        return st.session_state.documents[
            st.session_state.documents["tag"] == tag
        ]["title"].tolist()

    @staticmethod
    def get_document_summary_by_title(title):
        summary = st.session_state.documents.loc[
            st.session_state.documents["title"] == title, "summary"
        ].values

        # Check if a summary was found
        if summary.size > 0:
            return summary[0]
        else:
            return "尚未產生文件摘要"

    @staticmethod
    @st.cache_data
    def get_documents_by_permission(documents, user_documents):
        df = user_documents[
            (user_documents["username"] == st.session_state.username)
        ]

        my_document_ids = df[
            df["access_level"] == "write"
        ]["document_id"].tolist()
        shared_document_ids = df[
            df["access_level"] == "read"
        ]["document_id"].tolist()

        my_documents = documents[
            documents["document_id"].isin(my_document_ids)
        ].reset_index(drop=True)
        shared_documents = documents[
            documents["document_id"].isin(shared_document_ids)
        ].reset_index(drop=True)

        return my_documents, shared_documents

    @staticmethod
    def create_document_row(document_id, title, summary, tag):
        """Create a dictionary for a new document row."""
        return [{
            "id": document_id,
            "title": title,
            "tag": tag,
            "summary": summary,
        }]

    @staticmethod
    def create_user_document_row(user_document_id, document_id):
        """Create a dictionary for a new user document row with write access."""
        return [{
            "id": user_document_id,
            "username": st.session_state["username"],
            "document_id": document_id,
            "access_level": "write",
        }]

    @staticmethod
    def create_vector_rows(document_id, id_list):
        """Generate vector rows for a document."""
        return [[document_id, vector_id] for vector_id in id_list]

    @staticmethod
    def find_existing_documents(uploaded_files):
        """Check if the uploaded files already exist in the database."""
        titles = [Path(file.name).stem for file in uploaded_files]
        matching_titles = st.session_state.documents[
            st.session_state.documents["title"].isin(titles)
        ]["title"].tolist()

        if matching_titles:
            st.error(f"「{matching_titles[0]}」已經在資料庫中！")

        return matching_titles

    @staticmethod
    def get_document_ids(my_documents, selected_indices):
        """Retrieve document IDs for the selected rows."""
        return my_documents.loc[selected_indices, "id"].tolist()

    @staticmethod
    def _display_delete_confirmation(my_documents, selected_indices):
        """Display confirmation dialog for document deletion."""
        titles = my_documents.loc[selected_indices, "title"].tolist()
        title_str = "\n".join([f"- {title}" for title in titles])
        info_str = f"確認刪除以下文件？\n{title_str}"
        st.markdown(info_str)

        return st.button("確認")

    @staticmethod
    @st.dialog("刪除文件")
    def delete_documents(my_documents, selected_indices):
        # selected_indices = event.selection.rows

        if not DocumentManager._display_delete_confirmation(
            my_documents,
            selected_indices
        ):
            return

        with st.spinner(text="刪除文件中..."):
            document_ids = DocumentManager.get_document_ids(
                my_documents, 
                selected_indices
            )

            PineconeManager.delete_pinecone_documents(document_ids)
            SessionManager.delete_documents(document_ids)

            headers = {
                "Authorization": f"Bearer {st.session_state.token}"
            }

            for document_id in document_ids:
                response = requests.delete(
                    f"{st.secrets.BACKEND_URL}/documents/{document_id}",
                    headers=headers
                )
                if response.status_code != 200:
                    st.error("無法刪除文件！")
                    return

        st.session_state.delete_success = 1
        st.rerun()

    @staticmethod
    def _sync_to_google_sheets(documents):
        """Sync the processed documents and vectors to Google Sheets."""
        for i in stqdm(range(len(documents)), desc="同步至資料庫"):
            try:               
                headers = {
                    "Authorization": f"Bearer {st.session_state.token}"
                }
                
                # update documents
                response = requests.post(
                    f"{st.secrets.BACKEND_URL}/documents",
                    json={
                        "title": documents[i]["title"],
                        "tag": documents[i]["tag"],
                        "content": documents[i]["content"]
                    },
                    headers=headers
                )
                if response.status_code == 200:
                    document_id = response.json()["document_id"]
                    documents[i]["document_id"] = document_id
                else:
                    raise Exception(f"/documents responds status code {response.status_code}")

                # update vectors
                response = requests.post(
                    f"{st.secrets.BACKEND_URL}/vectors",
                    json={
                        "document_id": document_id,
                        "vector_ids": documents[i]["vectors"] 
                    },
                    headers=headers
                )
                if response.status_code != 200:
                    raise Exception(f"/vectors responds status code {response.status_code}")

                # update session_state
                new_document_row = DocumentManager.create_document_row(
                    document_id,
                    documents[i]["title"],
                    "摘要產生中...",
                    documents[i]["tag"]
                )

                SessionManager.upload_document(new_document_row)

            except Exception as e:
                print(f"Failed to upload {documents[i]['title']} to Google Sheets: {e}")
                st.session_state.upload_failure.append(documents[i]["title"])

    def _summarize(documents):
        """
        Calls the FastAPI /summarize endpoint.
        """
        
        try:
            for document in stqdm(documents, desc="傳送摘要請求"):
                # Define the payload with document data
                api_url = f"{st.secrets.BACKEND_URL}/documents/{document['document_id']}/summary"
                payload = {
                    "content": document["content"],
                    "username": st.session_state.username,
                }

                # Send the PUT request to the FastAPI endpoint
                response = requests.put(api_url, json=payload)
                if response.status_code != 200:
                    raise Exception(f"{response.status_code}")

        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP error occurred: {http_err}")
        except Exception as err:
            print(f"Other error occurred: {err}")

    @staticmethod
    def process_uploaded_files(uploaded_files, tag):
        """Process each uploaded file by loading, embedding, and uploading to Google Sheets."""
        st.session_state.upload_failure = []
        documents = []
        total_price = 0

        for i, uploaded_file in enumerate(uploaded_files):
            title = Path(uploaded_file.name).stem
            try:
                bytes_data = uploaded_file.getvalue()
                data = DocumentManager.load_pdf(
                    bytes_data, tag, title, desc=f"讀取第 {i+1} / {len(uploaded_files)} 份文件"
                )
                id_list, price = PineconeManager.upsert_documents(
                    data, desc=f"計算第 {i+1} / {len(uploaded_files)} 份文件特徵向量"
                )

                total_price += price
                content = "".join([page["content"] for page in data])
                documents.append({
                    "content": content,
                    "title": title,
                    "vectors": id_list,
                    "tag": tag
                })

            except Exception as e:
                print(f"Failed to process {title}: {e}")
                st.session_state.upload_failure.append(title)

        DocumentManager._sync_to_google_sheets(documents)
        # response = DocumentManager._summarize(documents)
        CostManager.update_cost(total_price)

    @staticmethod
    @st.dialog("上傳文件")
    def upload_document():
        uploaded_files = st.file_uploader(
            "選取檔案", accept_multiple_files=True, type="pdf")
        tag = st.selectbox("選取文件類別", st.session_state.tags["tag"].tolist())

        # Check for existing documents
        matching_titles = DocumentManager.find_existing_documents(
            uploaded_files)
        disabled = (len(matching_titles) != 0) or (len(uploaded_files) == 0)

        if st.button("提交", disabled=disabled, key="submit_button"):
            DocumentManager.process_uploaded_files(uploaded_files, tag)
            st.rerun()
