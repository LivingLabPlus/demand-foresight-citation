import streamlit as st
import streamlit_authenticator as stauth

import yaml
from yaml.loader import SafeLoader

st.set_page_config(page_title="Demand Foresight")

if "config" not in st.session_state:
    with open("users.yaml") as file:
        st.session_state.config = yaml.load(file, Loader=SafeLoader)


def empty_page():
    pass


# Define pages
chat_page = st.Page("chat.py", title="聊天",
                    icon=":material/chat:", default=True)
database_page = st.Page("database.py", title="資料庫", icon=":material/database:")
account_page = st.Page("account.py", title="帳戶", icon=":material/person:")
admin_page = st.Page("admin.py", title="文件管理", icon=":material/settings:")

# Initialize pages based on secrets
pages = [chat_page]
if st.secrets.modules.document_management:
    pages.append(database_page)
if st.secrets.modules.authentication:
    pages.append(account_page)


def run_navigation(pages):
    # Handle authentication if enabled
    pg = st.navigation({"選單": pages})
    pg.run()


def cleanup():
    # Ensure chat history would be updated after switching user
    if 'messages' in st.session_state:
        st.session_state.pop('messages')

    if 'documents' in st.session_state:
        st.session_state.pop('documents')


if st.secrets.modules.authentication:
    authenticator = stauth.Authenticate(
        st.session_state.config['credentials'],
        st.session_state.config['cookie']['name'],
        st.session_state.config['cookie']['key'],
        st.session_state.config['cookie']['expiry_days'],
    )

    try:
        authenticator.login()
    except LoginError as e:
        st.error(e)

    if st.session_state.username == 'admin':
        pages.insert(2, admin_page)

    if st.session_state.authentication_status:
        st.session_state.authenticator = authenticator
        run_navigation(pages)
    else:
        run_navigation([st.Page(empty_page)])
        cleanup()

        if st.session_state.authentication_status is False:
            st.error('使用者名稱/密碼不正確')
else:
    st.session_state['username'] = "default_user"
    run_navigation(pages)
