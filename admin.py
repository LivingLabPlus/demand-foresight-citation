import streamlit as st
import pandas as pd
import uuid
import yaml
import requests
import time
from yaml.loader import SafeLoader
from streamlit_tags import st_tags

from managers import SheetManager, SessionManager


@st.cache_data
def get_documents_visible_to_user(documents, user_documents, username):
    # Filter admin documents
    df = user_documents[user_documents['username'] == 'admin'].copy()

    # Check visibility based on presence in the user’s documents
    user_docs = user_documents[user_documents['username'] == username]
    df['is_visible'] = df['document_id'].isin(user_docs['document_id'])

    df = pd.merge(df, documents, on='document_id', how='inner')
    return df[['title', 'tag', 'is_visible', 'document_id']]


def hide_document(hided_documents, selected_username):
    # Get the session state DataFrame and filter it with vectorized conditions
    df = st.session_state.user_documents

    # Filter to get the indices of rows
    # that match the conditions in hided_documents
    matching_rows = df[(df['document_id'].isin(hided_documents['document_id'])) &
                       (df['username'] == selected_username) &
                       (df['access_level'] == 'read')]

    # Delete the matching rows from Google Sheets and update session state
    if not matching_rows.empty:
        SheetManager.delete_rows('userDocuments', matching_rows.index.tolist())
        st.session_state.user_documents = df.drop(
            matching_rows.index
        ).reset_index(drop=True)


def show_documents(added_documents, selected_username):
    rows_to_google_sheet, rows_in_memory = [], []

    for document_id in added_documents['document_id']:
        _id = str(uuid.uuid4())
        rows_to_google_sheet.append([
            _id, selected_username, document_id, 'read'
        ])
        rows_in_memory.append({
            'id': str(uuid.uuid4()),
            'username': selected_username,
            'document_id': document_id,
            'access_level': 'read'
        })

    SheetManager.append_rows('userDocuments', rows_to_google_sheet)
    new_df = pd.DataFrame(rows_in_memory)
    new_df = pd.concat([st.session_state.user_documents, new_df])
    new_df = new_df.reset_index(drop=True)
    st.session_state.user_documents = new_df


def manage_shared_documents():
    users = st.session_state.tokens["username"].tolist()
    users.remove("admin")
    selected_username = st.selectbox('**選擇使用者**', users)

    column_config = {
        'title': st.column_config.TextColumn(
            '文件名稱', help='文件名稱', max_chars=1024, width='large'
        ),
        'tag': st.column_config.TextColumn(
            '標籤',
            help='文件類別',
            width='small'
        ),
        'is_visible': st.column_config.CheckboxColumn(
            '查看權限',
            help='使用者與模型對話時，模型是否能找到此文件？',
            default=False,
        ),
        'document_id': None
    }

    visible_documents = get_documents_visible_to_user(
        st.session_state.documents,
        st.session_state.user_documents,
        selected_username
    )
    edited_documents = st.data_editor(
        visible_documents,
        column_config=column_config,
        hide_index=True,
    )

    if st.button(label="儲存"):
        column_name = "is_visible"

        # Identify changes
        changes = edited_documents[
            visible_documents[column_name] != edited_documents[column_name]
        ]

        # hide documents from user
        hided_documents = changes[changes[column_name] == False]
        hide_document(hided_documents, selected_username)

        # show documents to user
        added_documents = changes[changes[column_name] == True]
        show_documents(added_documents, selected_username)

        st.session_state.update_permission_success = 1
        st.rerun()


def add_new_user(username):
    api_url = f"{st.secrets.BACKEND_URL}/generate-token"
    payload = {
        "username": username,
        "spreadsheet_id": st.secrets.connection.spreadsheet_id,
        "spreadsheet_credentials": dict(st.secrets.connection.credentials),
    }

    response = requests.post(api_url, json=payload)
    if response.status_code == 200:
        token = response.json()["token"]
        SessionManager.add_token(username, token)
        return 1
    return 0


@st.dialog("新增使用者")
def add_users():
    disabled = False
    usernames = st_tags(label="", text="請輸入使用者名稱", maxtags=-1)
    existing_users = [
        user for user in usernames
        if user in st.session_state.tokens["username"].tolist()
    ]

    if len(usernames) == 0 or len(existing_users) != 0:
        disabled = True

    if len(existing_users) != 0:
        st.error(f"使用者「{existing_users[0]}」已經存在！")

    if st.button("確認", disabled=disabled):
        with st.spinner("新增使用者中..."):
            for user in usernames:
                add_user_success = add_new_user(user)
                if not add_user_success:
                    break

        if not add_user_success:
            st.error("無法新增使用者，請稍後再試")
            time.sleep(1)
        else:
            st.session_state.add_user_success = 1

        st.rerun()


def delete_users_confirmation(selected_indices):
    usernames = st.session_state.tokens.loc[
        selected_indices, "username"
    ].tolist()
    user_str = "\n".join([f"- {user}" for user in usernames])
    info_str = f"確認刪除以下使用者？\n{user_str}"
    st.markdown(info_str)
    return st.button("確認")


@st.dialog("刪除使用者")
def delete_users(selected_indices):
    if not delete_users_confirmation(selected_indices):
        return

    with st.spinner("刪除中..."):
        SheetManager.delete_rows("tokens", selected_indices)
        SessionManager.delete_tokens(selected_indices)

    st.session_state.delete_user_success = 1
    st.rerun()


def manage_login_links():
    column_config = {
        "username": st.column_config.TextColumn("使用者名稱"),
        "token": st.column_config.TextColumn("登入連結"),
    }

    event = st.dataframe(
        st.session_state.tokens,
        column_config=column_config,
        hide_index=True,
        on_select="rerun",
        selection_mode="multi-row"
    )

    columns = st.columns([1] * 9)
    with columns[0]:
        st.button("新增", on_click=add_users)

    with columns[1]:
        st.button(
            "刪除",
            type="primary",
            on_click=delete_users,
            args=(event.selection.rows,),
            disabled=not bool(event.selection.rows),
        )


SessionManager.initialize_page()
shared_documents_tab, login_links_tab = st.tabs(["共用文件", "登入連結"])
with shared_documents_tab:
    manage_shared_documents()
with login_links_tab:
    manage_login_links()
