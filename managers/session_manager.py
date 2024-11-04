import streamlit as st
import pandas as pd
from pinecone import Pinecone, ServerlessSpec

from .sheet_manager import SheetManager
from .pinecone_manager import PineconeManager


class SessionManager:
    datetime_format = "%Y-%m-%d %H:%M:%S"

    @staticmethod
    @st.cache_data
    def _transform_message_df(df, username):
        df = df[df['username'] == username]
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
    def _get_documents_by_user(documents, user_documents, username):
        # return None when cannot retrieve documents from database
        if documents is None or user_documents is None:
            return None

        document_ids = user_documents[
            user_documents["username"] == username
        ]["document_id"].tolist()

        documents_for_user = documents[
            documents["document_id"].isin(document_ids)
        ]
        return documents_for_user.reset_index(drop=True)

    @staticmethod
    def load_initial_data():
        # Load initial data into session state
        if "user_documents" not in st.session_state:
            st.session_state.user_documents = SheetManager.read(
                "userDocuments")

        if "documents" not in st.session_state:
            documents = SheetManager.read("documents")
            st.session_state.documents = SessionManager._get_documents_by_user(
                documents, st.session_state.user_documents, st.session_state.username
            )

        if "tags" not in st.session_state:
            st.session_state.tags = SheetManager.read("tags")

        # Initialize chat history
        if "messages" not in st.session_state:
            messages = SheetManager.read("messages")
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
    def is_data_loaded():
        return st.session_state.documents is not None and st.session_state.user_documents is not None

    @staticmethod
    def delete_documents(document_ids):
        """Update session state to reflect the deleted documents."""
        st.session_state.documents = st.session_state.documents[
            ~st.session_state.documents["document_id"].isin(document_ids)
        ].reset_index(drop=True)

        st.session_state.user_documents = st.session_state.user_documents[
            ~st.session_state.user_documents["document_id"].isin(document_ids)
        ].reset_index(drop=True)

    @staticmethod
    def upload_document(
        document_row,
        user_document_row
    ):
        """Update the local session state with the new document data."""
        st.session_state.documents = pd.concat(
            [st.session_state.documents, pd.DataFrame(document_row)]).reset_index(drop=True)
        st.session_state.user_documents = pd.concat(
            [st.session_state.user_documents, pd.DataFrame(user_document_row)]).reset_index(drop=True)

    @staticmethod
    def add_tags(tags):
        new_tag_row = [{"tag": tag} for tag in tags]
        new_df = pd.DataFrame(new_tag_row)
        new_df = pd.concat([st.session_state.tags, new_df])
        new_df = new_df.reset_index(drop=True)
        st.session_state.tags = new_df

    @staticmethod
    def delete_tags(row_indices):
        filtered_tags = st.session_state.tags.drop(row_indices)
        filtered_tags = filtered_tags.reset_index(drop=True)
        st.session_state.tags = filtered_tags
