import yaml
import time
import streamlit as st
from streamlit_authenticator.utilities import LoginError

if "reset" not in st.session_state:
    st.session_state.reset = 0

if "password_update_success" in st.session_state and st.session_state.password_update_success:
    st.toast("密碼更新成功！", icon="✅")
    st.session_state.password_update_success = 0

st.title("帳戶")
st.write(f"使用者名稱: `{st.session_state['username']}`.")

cols = st.columns([1, 2, 5])
with cols[0]:
    st.session_state["authenticator"].logout()

with cols[1]:
    if st.button("Reset password"):
        st.session_state.reset = not st.session_state.reset

if st.session_state.authentication_status and st.session_state.reset:
    try:
        if st.session_state["authenticator"].reset_password(
            st.session_state["username"],
            clear_on_submit=True
        ):
            with open("users.yaml", "w") as file:
                yaml.dump(st.session_state.config, file,
                          default_flow_style=False)

            st.session_state.reset = 0
            st.session_state.password_update_success = 1
            st.rerun()

    except Exception as e:
        st.error(e)
