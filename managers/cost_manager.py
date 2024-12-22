import streamlit as st
import requests


class CostManager:
    @staticmethod
    def update_cost(additional_cost):
        api_url = f"{st.secrets.BACKEND_URL}/update-cost"
        payload = {
            "username": st.session_state.username,
            "additional_cost": additional_cost,
            "spreadsheet_id": st.secrets.connection.spreadsheet_id,
            "spreadsheet_credentials": dict(st.secrets.connection.credentials),
        }

        response = requests.post(api_url, json=payload)
        if response.status_code != 200:
            st.error("無法更新花費金額")
            return

        st.session_state.cost.loc[
            st.session_state.cost["username"] == st.session_state.username, "cost"
        ] = response.json()["new_spending"]

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
