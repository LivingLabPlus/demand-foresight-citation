import streamlit as st
from streamlit_tags import st_tags
from .session_manager import SessionManager
from .sheet_manager import SheetManager


class TagManager:
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

        if st.button("確認", key="tag_confirm", disabled=disabled):
            with st.spinner("新增中..."):
                SheetManager.append_rows("tags", [[tag] for tag in tags])
                SessionManager.add_tags(tags)

            st.session_state.add_tag_success = 1
            st.rerun()

    @staticmethod
    def delete_tags(tag_event):
        row_indices = tag_event.selection.rows
        SheetManager.delete_rows("tags", row_indices)
        SessionManager.delete_tags(row_indices)
        st.session_state.delete_tag_success = 1
