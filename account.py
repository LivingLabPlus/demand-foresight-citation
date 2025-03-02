import yaml
import streamlit as st


def get_current_cost():
    cost = st.session_state.cost.loc[
        st.session_state.cost["username"] == st.session_state.username, "cost"
    ]
    return f"{cost.iloc[0]:.3f}" if not cost.empty else 0.0


st.title("帳戶")
st.write(f"使用者名稱: `{st.session_state['username']}`")
st.write(f"目前總共花費： ${get_current_cost()} USD")
