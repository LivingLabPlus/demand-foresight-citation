import streamlit as st
import streamlit_authenticator as stauth
from streamlit_authenticator.utilities import LoginError
from streamlit_cookies_manager import EncryptedCookieManager

import requests
import yaml
from yaml.loader import SafeLoader

st.set_page_config(page_title=st.secrets.PAGE_TITLE)

# Define pages
chat_page = st.Page("chat.py", title="聊天",
                    icon=":material/chat:", default=True)
database_page = st.Page("database.py", title="資料庫", icon=":material/database:")
admin_page = st.Page("admin.py", title="使用者管理", icon=":material/settings:")

# Initialize pages based on secrets
pages = [chat_page]
if st.secrets.modules.document_management:
    pages.append(database_page)


def run_navigation(pages):
    # Handle authentication if enabled
    pg = st.navigation({"選單": pages})
    pg.run()


def cleanup():
    # Ensure chat history would be updated after switching user
    if "messages" in st.session_state:
        st.session_state.pop("messages")

    if "documents" in st.session_state:
        st.session_state.pop("documents")


# This should be on top of your script
cookies = EncryptedCookieManager(
    # This prefix will get added to all your cookie names.
    # This way you can run your app on Streamlit Cloud without cookie name clashes with other apps.
    prefix="demand_foresight/",
    # You should really setup a long COOKIES_PASSWORD secret if you're running on Streamlit Cloud.
    password=st.secrets.COOKIES_PASSWORD,
)
if not cookies.ready():
    # Wait for the component to load and send us current cookies.
    st.stop()


def validate_token(token):
    """Send the token to the backend for validation."""
    api_url = f"{st.secrets.BACKEND_URL}/validate-token"
    payload = {
        "token": token,
        "spreadsheet_id": st.secrets.connection.spreadsheet_id,
        "spreadsheet_credentials": dict(st.secrets.connection.credentials),
    }
    response = requests.post(api_url, json=payload)
    if response.status_code == 200:
        user_info = response.json()
        st.session_state.username = user_info["username"]
        cookies["auth_token"] = token
        cookies.save()
    elif response.status_code == 500:
        st.error("Internal server error.")
    else:
        st.error("Invalid or expired token. Please request a new login link.")


def login():
    # Get token from query parameters
    token = st.query_params.get("token", None)

    # Check for a stored token
    stored_token = cookies.get("auth_token")

    if token:
        validate_token(token)
    elif stored_token:
        # Validate the token stored in cookies
        validate_token(stored_token)
    else:
        st.warning("Please use a provided link to log in.")


if "username" not in st.session_state:
    st.session_state.username = None
    login()

if st.session_state.username == 'admin':
    pages.insert(2, admin_page)
if st.session_state.username is not None:
    run_navigation(pages)
