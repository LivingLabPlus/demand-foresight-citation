import streamlit as st
import requests
import pandas as pd
from datetime import datetime


class CostManager:
    datetime_format = "%Y-%m-%d %H:%M:%S"

    @staticmethod
    def update_cost(additional_cost):
        api_url = f"{st.secrets.BACKEND_URL}/cost"
        timestamp = datetime.now().strftime(CostManager.datetime_format)
        payload = {
            "username": st.session_state.username,
            "cost": additional_cost,
            "timestamp": timestamp
        }

        response = requests.post(
            api_url, 
            json=payload,
            headers = {
                "Authorization": f"Bearer {st.session_state.token}"
            }
        )
        if response.status_code != 201:
            print("POST /cost status code:", response.status_code)
            st.error("無法更新花費金額")
            return


    @staticmethod
    def calculate_cost(prompt_tokens, completion_tokens, model):
        pricing = {
            "claude-3-5-sonnet-20241022": {
                "prompt_token": 3,
                "completion_token": 15
            },
            "text-embedding-3-small": {
                "prompt_token": 0.02,
                "completion_token": 0
            },
        }

        if model not in pricing:
            st.error(
                f"The selected model '{model}' is not supported for pricing calculations.")
            return 0

        return (
            pricing[model]["prompt_token"] * prompt_tokens
            + pricing[model]["completion_token"] * completion_tokens
        ) / 1e6


    @staticmethod
    def get_cost_payload():
        today = pd.Timestamp.today().normalize()
        start_dates = pd.date_range(end=today, periods=12, freq='MS')  # 每月第一天
        end_dates = pd.date_range(end=today, periods=12, freq='ME')  # 每月最後一天

        # 轉成 JSON 格式
        data = [
            {
                "month": start.strftime("%Y-%m"),
                "start_date": start.strftime('%Y-%m-%d'), 
                "end_date": end.strftime('%Y-%m-%d'),            
            } 
            for start, end in zip(start_dates, end_dates)
        ]
        return data


    @st.cache_data
    @staticmethod
    def get_user_usage(username=None):
        dates = CostManager.get_cost_payload()
        base_url = f"{st.secrets.BACKEND_URL}/cost"
        headers = {
            "Authorization": f"Bearer {st.session_state.token}"
        }
        
        # Retrieve user usage data over the past year.
        cost_list = []
        with st.spinner("獲取使用者數據中..."):    
            for date in dates:
                params = {
                    "start_date": date["start_date"],
                    "end_date": date["end_date"]
                }
                if username is not None:
                    params["username"] = username

                response = requests.get(base_url, params=params, headers=headers)
                if response.status_code == 200:
                    cost_list.append({
                        "date": date["month"],
                        "cost": response.json()["cost"]
                    })
                else:
                    print("GET /cost error")
                    print("params:", params)
                    print(response.json()["error"])
        
            # Retrieve the sum of all cost
            params = {"username": username} if username is not None else None
            response = requests.get(base_url, params=params, headers=headers)
            if response.status_code == 200:
                all_cost = response.json()["cost"]
            else:
                print("GET /cost error")
                print("params:", params)
                print(response.json()["error"])
                all_cost = -1

        return all_cost, pd.DataFrame(cost_list)
