import streamlit as st
import pandas as pd
import requests
from pinecone import Pinecone, ServerlessSpec

from .pinecone_manager import PineconeManager


class SessionManager:
    datetime_format = "%Y-%m-%d %H:%M:%S"

    @staticmethod
    @st.cache_data
    def _transform_message_df(df, username):
        df = df.loc[:, df.columns != 'username']  # Drop without inplace=True

        # Ensure timestamp column is in datetime format
        df['timestamp'] = pd.to_datetime(
            df['timestamp'],
            format=SessionManager.datetime_format
        )

        # Group by chat_id and title, then sort by timestamp
        grouped = df.groupby(['chat_id', 'title'])

        # Prepare the final output
        result = []

        for (chat_id, title), group in grouped:
            messages = group[['role', 'content', 'timestamp']].sort_values(
                'timestamp').to_dict(orient='records')
            chat_entry = {
                'chat_id': chat_id,
                'title': title,
                'messages': messages
            }
            result.append(chat_entry)

        # result format:
        # [
        #     {
        #         "chat_id": "string",
        #         "title": "string",
        #         "messages": [
        #             {
        #                 "role": "string",
        #                 "content": "string",
        #                 "timestamp": "datetime"
        #             }
        #         ]
        #     }
        # ]

        sorted_result = sorted(
            result, key=lambda x: x['messages'][-1]['timestamp'], reverse=True)
        return sorted_result

    @staticmethod
    def load_documents():
        headers = {
            "Authorization": f"Bearer {st.session_state.token}"
        }
        api_url = f"{st.secrets.BACKEND_URL}/documents"
        response = requests.get(api_url, headers=headers)
        if response.status_code == 200:
            documents = response.json()["documents"]
            st.session_state.documents = pd.DataFrame(documents)
        else:
            st.error("無法讀取文件")

    @staticmethod
    def token_to_link(token):
        return f"{st.secrets.FRONTEND_URL}/?token={token}"

    @staticmethod
    def load_initial_data():
        # Load initial data into session state
        username = st.session_state.username
        headers = {
            "Authorization": f"Bearer {st.session_state.token}"
        }

        if username == st.secrets.ADMIN_NAME:
            if "tokens" not in st.session_state:
                response = requests.get(
                    f"{st.secrets.BACKEND_URL}/users",
                    headers=headers
                )

                if response.status_code == 200:
                    users = response.json()["users"]
                    tokens = pd.DataFrame(users)
                    tokens["token"] = tokens["token"].apply(SessionManager.token_to_link)
                    tokens["token_expire_datetime"] = pd.to_datetime(tokens["token_expire_datetime"])
                    st.session_state.tokens = tokens
                else:
                    st.error("無法獲取使用者資料！")

        if "documents" not in st.session_state:
            SessionManager.load_documents()

        if "tags" not in st.session_state:
            api_url = f"{st.secrets.BACKEND_URL}/tags"
            response = requests.get(api_url, headers=headers)
            
            if response.status_code == 200:
                st.session_state.tags = pd.DataFrame(response.json()["tags"])
            else:
                st.error("無法讀取標籤")

        if "cost" not in st.session_state:
            response = requests.get(
                f"{st.secrets.BACKEND_URL}/cost",
                headers=headers
            )
            if response.status_code == 200:
                st.session_state.cost = response.json()["cost"]
            else:
                st.error("無法讀取花費金額")

        # Initialize chat history
        if "messages" not in st.session_state:
            api_url = f"{st.secrets.BACKEND_URL}/messages"
            response = requests.get(api_url, headers=headers)

            if response.status_code == 200:
                messages = pd.DataFrame(response.json()["messages"])
            else:
                messages = None
                st.error("無法讀取標籤")
            
            if messages is not None:
                st.session_state.messages = SessionManager._transform_message_df(
                    messages, st.session_state.username)
            else:
                st.session_state.messages = []

        if "index" not in st.session_state:
            st.session_state.index = PineconeManager.get_index()


    @staticmethod
    def handle_session_messages():
        """Display toast notifications based on session state flags."""
        session_flags = {
            "upload_failure": "",
            "delete_success": "資料刪除成功！",
            "add_tag_success": "標籤新增成功！",
            "delete_tag_success": "標籤刪除成功！",
            "modify_tag_success": "標籤編輯成功！",
            "update_permission_success": "變更成功！",
            "add_user_success": "使用者新增成功！",
            "delete_user_success": "使用者刪除成功！",
            "modify_user_expire_time_success": "帳戶到期時間已更新！",
        }

        for key, message in session_flags.items():
            if key not in st.session_state:
                continue

            if key == "upload_failure":
                if len(st.session_state.upload_failure) == 0:
                    st.toast("資料上傳成功！", icon="✅")
                else:
                    st.toast(f"無法上傳文件，請稍後再試", icon="❌")

            else:
                st.toast(message, icon="✅")

            st.session_state.pop(key)

    @staticmethod
    def initialize_page():
        # Main function to initialize app and handle session state setup
        with st.spinner("讀取資料中..."):
            SessionManager.load_initial_data()
        SessionManager.handle_session_messages()

    @staticmethod
    def is_data_loaded():
        return st.session_state.documents is not None

    @staticmethod
    def delete_documents(document_ids):
        """Update session state to reflect the deleted documents."""
        st.session_state.documents = st.session_state.documents[
            ~st.session_state.documents["id"].isin(document_ids)
        ].reset_index(drop=True)

    @staticmethod
    def upload_document(document_row):
        """Update the local session state with the new document data."""
        st.session_state.documents = pd.concat([
            st.session_state.documents, 
            pd.DataFrame(document_row)
        ]).reset_index(drop=True)

    @staticmethod
    def add_tags(tag_rows):
        new_df = pd.DataFrame(tag_rows)
        new_df = pd.concat([st.session_state.tags, new_df])
        new_df = new_df.reset_index(drop=True)
        st.session_state.tags = new_df

    @staticmethod
    def delete_tags(row_indices):
        filtered_tags = st.session_state.tags.drop(row_indices)
        filtered_tags = filtered_tags.reset_index(drop=True)
        st.session_state.tags = filtered_tags

    @staticmethod
    def modify_tag(current_tag, new_tag):
        st.session_state.documents["tag"] = st.session_state.documents["tag"].replace(
            current_tag, new_tag
        )

    @staticmethod
    def add_token(username, token, token_expire_datetime):
        link = SessionManager.token_to_link(token)
        new_token_row = [{
            "username": username, 
            "token": link,
            "token_expire_datetime": pd.Timestamp(token_expire_datetime)
        }]
        new_df = pd.DataFrame(new_token_row)
        new_df = pd.concat([st.session_state.tokens, new_df])
        new_df = new_df.reset_index(drop=True)
        st.session_state.tokens = new_df

    @staticmethod
    def delete_tokens(row_indices):
        filtered_tokens = st.session_state.tokens.drop(row_indices)
        filtered_tokens = filtered_tokens.reset_index(drop=True)
        st.session_state.tokens = filtered_tokens
