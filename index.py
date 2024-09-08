import streamlit as st
import streamlit_authenticator as stauth

import yaml
from yaml.loader import SafeLoader

st.set_page_config(page_title="Demand Foresight")

with open('users.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)

# if 'authenticator' not in st.session_state:
authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)

# Call the login method
name, authentication_status, username = authenticator.login()

def empty_page():
    pass

# st.write(st.session_state['authentication_status'])
if authentication_status:
    database_page = st.Page("database.py", title="資料庫", icon=":material/settings:")
    chat_page = st.Page("chat.py", title="聊天", icon=":material/settings:", default=True)
    account_page = st.Page("account.py", title="帳戶", icon=":material/settings:")

    # Store username and logout function in session state
    st.session_state['username'] = username
    st.session_state['authenticator'] = authenticator

    pg = st.navigation({"選單": [chat_page, database_page, account_page]})
    pg.run()
elif authentication_status is False:
    pg = st.navigation([st.Page(empty_page)])
    pg.run()
    st.error('使用者名稱/密碼不正確')
elif authentication_status is None:
    pg = st.navigation([st.Page(empty_page)])
    pg.run()
    