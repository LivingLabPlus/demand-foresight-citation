import streamlit as st
import pandas as pd
import uuid
import yaml
from yaml.loader import SafeLoader

from managers import DocumentManager

dm = DocumentManager()

with open('users.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)

users = list(config['credentials']['usernames'].keys())
users.remove('admin')

selected_username = st.selectbox('**選擇使用者**', users)

with st.spinner("讀取資料中..."):
    if "user_documents" not in st.session_state:
        st.session_state.user_documents = dm.read(
            worksheet_name="userDocuments")

    if "documents" not in st.session_state:
        documents = DocumentManager.read("documents")
        st.session_state.documents = DocumentManager.get_documents_by_user(
            documents,
            st.session_state.user_documents,
            st.session_state.username
        )

if "update_permission_success" in st.session_state and st.session_state.update_permission_success:
    st.toast("變更成功！", icon="✅")
    st.session_state.update_permission_success = 0


@st.cache_data
def get_documents_visible_to_user(documents, user_documents, username):
    # Filter admin documents
    df = user_documents[user_documents['username'] == 'admin'].copy()

    # Check visibility based on presence in the user’s documents
    user_docs = user_documents[user_documents['username'] == username]
    df['is_visible'] = df['document_id'].isin(user_docs['document_id'])

    df = pd.merge(df, documents, on='document_id', how='inner')
    return df[['title', 'tag', 'is_visible', 'document_id']]


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


def hide_document(hided_documents):
    # Get the session state DataFrame and filter it with vectorized conditions
    df = st.session_state.user_documents

    # Filter to get the indices of rows
    # that match the conditions in hided_documents
    matching_rows = df[(df['document_id'].isin(hided_documents['document_id'])) &
                       (df['username'] == selected_username) &
                       (df['access_level'] == 'read')]

    # Delete the matching rows from Google Sheets and update session state
    if not matching_rows.empty:
        dm.delete_rows('userDocuments', matching_rows.index.tolist())
        st.session_state.user_documents = df.drop(
            matching_rows.index
        ).reset_index(drop=True)


def show_documents(added_documents):
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

    dm.append_rows('userDocuments', rows_to_google_sheet)
    new_df = pd.DataFrame(rows_in_memory)
    new_df = pd.concat([st.session_state.user_documents, new_df])
    new_df = new_df.reset_index(drop=True)
    st.session_state.user_documents = new_df


def track_changes_in_visible_column(column_name='is_visible'):
    # Identify changes
    changes = edited_documents[
        visible_documents[column_name] != edited_documents[column_name]
    ]

    # hide documents from user
    hided_documents = changes[changes[column_name] == False]
    hide_document(hided_documents)

    # show documents to user
    added_documents = changes[changes[column_name] == True]
    show_documents(added_documents)

    st.session_state.update_permission_success = 1


st.button(label='儲存', on_click=track_changes_in_visible_column)
