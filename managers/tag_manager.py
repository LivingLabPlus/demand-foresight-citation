import requests
import streamlit as st
from streamlit_tags import st_tags
from .session_manager import SessionManager


class TagManager:
    @staticmethod
    def add_tag_to_database(tag):
        headers = {
            "Authorization": f"Bearer {st.session_state.token}"
        }
        response = requests.post(
            f"{st.secrets.BACKEND_URL}/tags",
            json={
                "username": st.session_state.username,
                "tag": tag
            },
            headers=headers
        )
        return response.json()["tag_id"] if response.status_code == 200 else None

    @staticmethod
    def process_tags(tags):
        """Add tags to the database and return successfully added tags."""
        tag_rows = []
        for tag in tags:
            tag_id = TagManager.add_tag_to_database(tag)
            if tag_id is None:
                st.error("無法新增標籤！")
                return None
            tag_rows.append({"tag_id": tag_id, "tag": tag})
        return tag_rows

    @staticmethod
    @st.dialog("新增標籤")
    def add_tags():
        disabled = False
        tags = st_tags(label="", text="請輸入標籤", maxtags=-1)
        existing_tags = [
            tag for tag in tags
            if tag in st.session_state.tags["tag"].tolist()
        ]

        if len(tags) == 0 or len(existing_tags) != 0:
            disabled = True

        if len(existing_tags) != 0:
            st.error(f"標籤「{existing_tags[0]}」已經在資料庫中！")

        tag_rows = []
        if st.button("確認", key="tag_confirm", disabled=disabled):
            with st.spinner("新增中..."):
                tag_rows = TagManager.process_tags(tags)
                if tag_rows is not None:
                    SessionManager.add_tags(tag_rows)
                    st.session_state.add_tag_success = 1
                    st.rerun()

    @staticmethod
    def delete_tags(tag_event):
        row_indices = tag_event.selection.rows
        tag_ids = st.session_state.tags.loc[row_indices, "tag_id"].tolist()
        headers = {
            "Authorization": f"Bearer {st.session_state.token}"
        }

        for tag_id in tag_ids:   
            response = requests.delete(
                f"{st.secrets.BACKEND_URL}/tags/{tag_id}",
                headers=headers
            )
            if response.status_code != 200:
                st.error("無法刪除標籤！")
                return

        SessionManager.delete_tags(row_indices)
        st.session_state.delete_tag_success = 1


    @staticmethod
    @st.dialog("編輯標籤")
    def edit_tag(selected_rows):
        selected_row = selected_rows[0]
        current_tag = st.session_state.tags.loc[selected_row, "tag"]
        tag_id = st.session_state.tags.loc[selected_row, "tag_id"]
        st.markdown(f"**目前選擇的標籤：** {current_tag}")
        new_tag = st.text_input("請輸入新的標籤名稱")

        is_existed = new_tag in st.session_state.tags["tag"].tolist()
        disabled = False

        if not new_tag or is_existed:
            disabled = True

        if is_existed:
            st.error(f"標籤「{new_tag}」已經存在！")

        if st.button("確認", disabled=disabled):
            with st.spinner("修改中..."):
                headers = {
                    "Authorization": f"Bearer {st.session_state.token}"
                }
                response = requests.put(
                    f"{st.secrets.BACKEND_URL}/tags/{tag_id}",
                    json={"new_tag": new_tag},
                    headers=headers
                )
                if response.status_code != 200:
                    st.error("修改標籤失敗！")
                    return

                st.session_state.documents["tag"] = st.session_state.documents["tag"].replace(
                    current_tag, new_tag
                )
                st.session_state.tags.loc[selected_row, "tag"] = new_tag

            st.session_state.modify_tag_success = 1
            st.rerun()

