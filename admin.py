import streamlit as st
import pandas as pd
import uuid
import yaml
import requests
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta
from yaml.loader import SafeLoader
from streamlit_tags import st_tags

from managers import SessionManager, CostManager


def add_new_user(username, token_expire_datetime):
    api_url = f"{st.secrets.BACKEND_URL}/users"
    headers = {
        "Authorization": f"Bearer {st.session_state.token}"
    }
    payload = {
        "username": username,
        "token_expire_datetime": token_expire_datetime.isoformat()
    }

    response = requests.post(api_url, json=payload, headers=headers)
    if response.status_code == 200:
        token = response.json()["token"]
        SessionManager.add_token(username, token, token_expire_datetime)
        return 1
    else:
        print("POST /user error")
        print("status code:", response.status_code)
        print("error:", response.json()["error"])
    return 0


@st.dialog("新增使用者")
def add_users():
    disabled = False
    usernames = st_tags(label="", text="請輸入使用者名稱", maxtags=-1)
    expire_date = st.date_input(
        "到期時間",
        value=datetime.today() + relativedelta(months=6), 
        min_value=datetime.today()
    )
    existing_users = [
        user for user in usernames
        if user in st.session_state.tokens["username"].tolist()
    ]

    if len(usernames) == 0 or len(existing_users) != 0 or expire_date is None:
        disabled = True

    if len(existing_users) != 0:
        st.error(f"使用者「{existing_users[0]}」已經存在！")

    if st.button("確認", disabled=disabled):
        with st.spinner("新增使用者中..."):
            for user in usernames:
                add_user_success = add_new_user(user, expire_date)
                if not add_user_success:
                    break

        if not add_user_success:
            st.error("無法新增使用者，請稍後再試")
            time.sleep(1)
        else:
            st.session_state.add_user_success = 1

        st.rerun()


@st.dialog("修改帳戶到期時間")
def modify_user_expire_time(selected_rows):
    selected_row = selected_rows[0]
    current_expiry = st.session_state.tokens.loc[selected_row, 'token_expire_datetime']
    current_user = st.session_state.tokens.loc[selected_row, 'username']
    st.markdown(f"**目前選擇的使用者:** `{current_user}`")
    new_expiry = st.date_input("選擇新的過期時間", value=current_expiry)
    
    if st.button("確認修改"):
        with st.spinner("修改中..."):
            headers = {
                "Authorization": f"Bearer {st.session_state.token}"
            }
            response = requests.put(
                f"{st.secrets.BACKEND_URL}/users",
                json={
                    "username": current_user,
                    "token_expire_datetime": new_expiry.isoformat()
                },
                headers=headers
            )
            if response.status_code != 200:
                st.error("無法更新到期時間！")
            else:
                # print("modify user expire time response:", response.json())
                st.session_state.tokens.loc[
                    selected_row, "token_expire_datetime"
                ] = pd.Timestamp(new_expiry)
                st.session_state.modify_user_expire_time_success = 1
                st.rerun()
                # new_token = response.json()["token"]
                # st.session_state.tokens.loc[
                #     selected_row, "token"
                # ] = SessionManager.token_to_link(new_token)
                


def delete_users_confirmation(selected_indices):
    usernames = st.session_state.tokens.loc[
        selected_indices, "username"
    ].tolist()
    user_str = "\n".join([f"- {user}" for user in usernames])
    info_str = f"確認刪除以下使用者？\n{user_str}"
    st.markdown(info_str)
    return st.button("確認")


@st.dialog("刪除使用者")
def delete_users(selected_indices):
    if not delete_users_confirmation(selected_indices):
        return

    headers = {
        "Authorization": f"Bearer {st.session_state.token}"
    }

    with st.spinner("刪除中..."):
        usernames = st.session_state.tokens.loc[selected_indices, "username"].tolist()
        for username in usernames:
            response = requests.delete(
                f"{st.secrets.BACKEND_URL}/users/{username}",
                headers=headers
            )
            if response.status_code != 200:
                st.error(f"刪除使用者 {username} 失敗！")
                return

        SessionManager.delete_tokens(selected_indices)

    st.session_state.delete_user_success = 1
    st.rerun()


@st.cache_data
def get_user_documents(username):
    headers = {
        "Authorization": f"Bearer {st.session_state.token}"
    }
    response = requests.get(
        f"{st.secrets.BACKEND_URL}/documents",
        params={"username": username},
        headers=headers
    )     
    if response.status_code != 200:
        return None
    
    documents = response.json()["documents"]
    return pd.DataFrame(documents)


def display_user_data(selected_rows):
    if not selected_rows:
        return

    selected_user = st.session_state.tokens.loc[selected_rows[0], "username"]

    # display user usage
    st.markdown("---")
    all_cost, monthly_cost = CostManager.get_user_usage(selected_user)
    if all_cost == -1:
        st.error("無法獲取使用額度！")
    else:
        st.markdown(f"**總共花費金額:** {all_cost:.2f} $USD")

        if len(monthly_cost) != 0:
            st.markdown("**過去一年花費紀錄:**")
            st.bar_chart(
                monthly_cost,
                x="date",
                y="cost",
                x_label="月份",
                y_label="花費金額（$USD）"
            )

    # display user documents
    st.markdown("---")
    st.markdown("**上傳文件**")
    documents = get_user_documents(selected_user)
    column_config = {
        "id": None,
        "title": st.column_config.TextColumn(
            "文件名稱",
            help="文件名稱",
            max_chars=1024,
            width="large"
        ),
        "tag": st.column_config.TextColumn(
            "標籤",
            help="文件類別",
        ),
        "summary": None,
        "created_at": st.column_config.DatetimeColumn(
            "上傳時間",
            format="YYYY-MM-DD HH:mm"
        )
    }
    st.dataframe(
        documents,
        column_config=column_config,
        use_container_width=True,
        hide_index=True,
    )
    


def manage_login_links():
    column_config = {
        "username": st.column_config.TextColumn("使用者名稱"),
        "token": st.column_config.TextColumn("登入連結", width="large"),
        "token_expire_datetime": st.column_config.DatetimeColumn(
            "帳戶到期時間",
            format="YYYY-MM-DD"
        )
    }

    event = st.dataframe(
        st.session_state.tokens,
        column_config=column_config,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row"
    )

    columns = st.columns([1, 1, 2, 5])
    with columns[0]:
        st.button("新增", on_click=add_users)

    with columns[1]:
        st.button(
            "刪除",
            type="primary",
            on_click=delete_users,
            args=(event.selection.rows,),
            disabled=not bool(event.selection.rows),
        )

    with columns[2]:
        st.button(
            "修改到期時間",
            on_click=modify_user_expire_time,
            args=(event.selection.rows,),
            disabled=not bool(event.selection.rows),
        )

    display_user_data(event.selection.rows)


SessionManager.initialize_page()
st.subheader("使用者管理")
st.text("選取使用者以展示更多資料")
manage_login_links()
