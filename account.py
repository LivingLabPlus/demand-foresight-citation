import yaml
import streamlit as st

from managers import CostManager


st.subheader("帳戶")
st.markdown(f"**使用者名稱:** `{st.session_state['username']}`")
all_cost, monthly_cost = CostManager.get_user_usage()
if all_cost == -1 or len(monthly_cost) != 12:
    st.error("無法獲取使用額度！")
else:
    st.markdown(f"**總共花費金額:** {all_cost:.2f} $USD")
    st.markdown("**過去一年花費紀錄:**")
    st.bar_chart(
        monthly_cost,
        x="date",
        y="cost",
        x_label="月份",
        y_label="花費金額（$USD）"
    )
