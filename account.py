import streamlit as st

st.title("帳戶")
st.write(f"This is the account page for user: `{st.session_state["username"]}`.")
st.session_state['authenticator'].logout()
