import streamlit as st
from streamlit_cookies_manager import EncryptedCookieManager

import requests
import yaml
from yaml.loader import SafeLoader
from datetime import datetime

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

# Define pages
chat_page = st.Page("chat.py", title="聊天",
                    icon=":material/chat:", default=True)
database_page = st.Page("database.py", title="資料庫", icon=":material/database:")
admin_page = st.Page("admin.py", title="使用者管理", icon=":material/settings:")
account_page = st.Page("account.py", title="帳戶", icon=":material/person:")

# Initialize pages based on secrets
pages = [chat_page]
if st.secrets.modules.document_management:
    pages.append(database_page)
pages.append(account_page)


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


def convert_expire_time(date_str):
    # Parse the input string into a datetime object
    dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%fZ")

    # Convert it to the desired format
    return dt.strftime("%Y-%m-%d")


def validate_token(token):
    """Send the token to the backend for validation."""
    api_url = f"{st.secrets.BACKEND_URL}/users/me"

    # Define the authentication header
    headers = {
        "Authorization": f"Bearer {token}"
    }

    # Send the GET request with headers
    response = requests.get(api_url, headers=headers)

    # Check the response status
    if response.status_code == 200:
        user_info = response.json()
        st.session_state.username = user_info["username"]
        st.session_state.token_expire_date = convert_expire_time(user_info["token_expire_datetime"])
        st.session_state.token = token
        
        # save token in cookies
        cookies["auth_token"] = token
        cookies.save()
    elif response.status_code == 500:
        st.error("Internal server error.")


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


if "username" not in st.session_state:
    st.session_state.username = None
    login()

if st.session_state.username == st.secrets.ADMIN_NAME:
    pages.insert(2, admin_page)
if st.session_state.username is not None:
    run_navigation(pages)
else:
    st.warning("Invalid or expired token. Please request a new login link.")
