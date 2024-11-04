import streamlit as st
from openai import OpenAI


class LLMManger:
    def __init__(self):
        self.openai_client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

    def get_embeddings(self, texts, model="text-embedding-3-small"):
        embeddings = self.openai_client.embeddings.create(
            input=texts, model=model)
        embeddings = [d.embedding for d in embeddings.data]
        return embeddings
