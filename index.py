import streamlit as st
import streamlit_authenticator as stauth

import yaml
from yaml.loader import SafeLoader

st.set_page_config(page_title="Demand Foresight")

with open('users.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)

def empty_page():
    pass

# Define pages
database_page = st.Page("database.py", title="資料庫", icon=":material/settings:")
chat_page = st.Page("chat.py", title="聊天", icon=":material/settings:", default=True)
account_page = st.Page("account.py", title="帳戶", icon=":material/settings:")

# Initialize pages based on secrets
pages = [chat_page]
if st.secrets.modules.document_management:
    pages.append(database_page)
if st.secrets.modules.authentication:
    pages.append(account_page)

# Handle authentication if enabled
def run_navigation(pages):
    pg = st.navigation({"選單": pages})
    pg.run()

if st.secrets.modules.authentication:
    authenticator = stauth.Authenticate(
        config['credentials'],
        config['cookie']['name'],
        config['cookie']['key'],
        config['cookie']['expiry_days']
    )
    name, authentication_status, username = authenticator.login()

    if authentication_status:
        st.session_state['username'] = username
        run_navigation(pages)
    else:
        run_navigation([st.Page(empty_page)])
        if authentication_status is False:
            st.error('使用者名稱/密碼不正確')
else:
    st.session_state['username'] = "default_user"
    run_navigation(pages)
