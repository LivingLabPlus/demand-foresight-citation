import uuid
import pandas as pd
import streamlit as st
from streamlit_gsheets import GSheetsConnection
from streamlit_tags import st_tags
from pathlib import Path
from tqdm import tqdm
from stqdm import stqdm

from managers import (
    DocumentManager,
    PineconeManager,
    SessionManager,
    SheetManager,
    TagManager
)


# Main function to initialize app and handle session state setup
def initialize_page():
    with st.spinner("讀取資料中..."):
        SessionManager.load_initial_data()
    SessionManager.handle_session_messages()


def display_documents_interface():
    """Display main interface for managing documents and tags."""
    my_documents, shared_documents = DocumentManager.get_documents_by_permission(
        st.session_state.documents, st.session_state.user_documents)

    tab_names = ["我的文件"]
    if st.secrets.modules.document_sharing:
        tab_names.append("共用文件")
    if st.secrets.modules.document_summarization:
        tab_names.append("文件摘要")
    if st.secrets.modules.tag_editing:
        tab_names.append("編輯標籤")
    tabs = st.tabs(tab_names)

    with tabs[0]:
        display_my_documents(my_documents)

    tab_index = 1
    if st.secrets.modules.document_sharing:
        with tabs[tab_index]:
            display_shared_documents(shared_documents)
        tab_index += 1

    if st.secrets.modules.document_summarization:
        with tabs[tab_index]:
            display_document_summaries()
        tab_index += 1

    if st.secrets.modules.tag_editing:
        with tabs[tab_index]:
            display_tag_management()
        tab_index += 1


def display_my_documents(my_documents):
    """Display and handle actions for '我的文件' tab."""
    event = st.dataframe(
        my_documents,
        column_config=define_column_config(),
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="multi-row"
    )

    columns = st.columns([1] * 9)
    with columns[0]:
        st.button(
            label="上傳",
            on_click=DocumentManager.upload_document,
            key="upload_button"
        )

    with columns[1]:
        st.button(
            "刪除",
            type="primary",
            on_click=DocumentManager.delete_documents,
            args=(my_documents, event.selection.rows),
            disabled=not bool(event.selection.rows),
            key="delete_button"
        )


def display_shared_documents(shared_documents):
    """Display '共用文件' tab."""
    st.dataframe(
        shared_documents,
        column_config=define_column_config(),
        use_container_width=True,
        hide_index=True,
        on_select="ignore"
    )


def display_document_summaries():
    """Display '文件摘要' tab."""
    selected_tag = st.selectbox(
        "選取文件類別", st.session_state.tags["tag"].tolist())
    titles = DocumentManager.get_document_titles_by_tag(selected_tag)
    selected_title = st.selectbox("選取文件", titles)

    if selected_title is not None:
        summary = DocumentManager.get_document_summary_by_title(selected_title)
        st.markdown(summary)


def display_tag_management():
    """Display and handle actions for '編輯標籤' tab."""
    if st.session_state.username == "admin":
        tag_event = st.dataframe(
            st.session_state.tags,
            on_select="rerun",
            selection_mode="multi-row",
            hide_index=True,
            column_config={"tag": st.column_config.TextColumn(
                "標籤", width="medium")}
        )

        columns = st.columns([1] * 9)
        with columns[0]:
            st.button(
                "新增",
                on_click=TagManager.add_tags,
                key="add_tags_button"
            )

        with columns[1]:
            st.button(
                "刪除",
                type="primary",
                on_click=TagManager.delete_tags,
                args=(tag_event,),
                disabled=not bool(tag_event.selection.rows),
                key="delete_tags_button"
            )
    else:
        st.info("只有管理者可以編輯標籤")


def define_column_config():
    """Define column configuration for dataframes."""
    return {
        "document_id": None,
        "title": st.column_config.TextColumn(
            "文件名稱",
            help="文件名稱",
            max_chars=1024,
            width="large"
        ),
        "tag": st.column_config.TextColumn(
            "標籤",
            help="文件類別",
            width="small"
        ),
        "summary": None,
    }


# Main execution
initialize_page()
st.header("資料庫")
if SessionManager.is_data_loaded():
    display_documents_interface()
else:
    st.error("無法讀取資料，請稍候並重新整理")
