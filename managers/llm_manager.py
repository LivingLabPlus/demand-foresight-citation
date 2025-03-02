import streamlit as st
import google.generativeai as genai
from openai import OpenAI
from .cost_manager import CostManager


class LLMManger:
    def __init__(self):
        self.openai_client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

    def get_embeddings(self, texts, model="text-embedding-3-small"):
        response = self.openai_client.embeddings.create(
            input=texts, model=model)

        embeddings = [d.embedding for d in response.data]
        pricing = CostManager.calculate_cost(
            response.usage.prompt_tokens, 0, model)
        return embeddings, pricing
