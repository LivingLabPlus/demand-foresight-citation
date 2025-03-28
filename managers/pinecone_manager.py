import hashlib
import requests
import streamlit as st
from stqdm import stqdm
from pinecone import Pinecone, ServerlessSpec

from .llm_manager import LLMManger


class PineconeManager:
    @staticmethod
    def get_index():
        pc = Pinecone(api_key=st.secrets["PINECONE_API_KEY"])
        index_name = st.secrets["INDEX_NAME"]
        spec = ServerlessSpec(
            cloud="aws", region="us-east-1"
        )

        existing_indexes = [
            index_info["name"] for index_info in pc.list_indexes()
        ]

        # check if index already exists (it shouldn't if this is first time)
        if index_name not in existing_indexes:
            # if does not exist, create index
            pc.create_index(
                index_name,
                dimension=1536,  # dimensionality of text-embedding-3-small embeddings
                metric="dotproduct",
                spec=spec
            )
            # wait for index to be initialized
            while not pc.describe_index(index_name).status["ready"]:
                sleep(1)

        # connect to index
        index = pc.Index(index_name)
        return index

    @staticmethod
    def delete_pinecone_documents(selected_document_ids):
        headers = {
            "Authorization": f"Bearer {st.session_state.token}"
        }
        for document_id in selected_document_ids:
            # get vector ids of the document from database   
            response = requests.get(
                f"{st.secrets.BACKEND_URL}/vectors",
                params={"document_id": document_id},
                headers=headers
            )
            if response.status_code == 200:
                vector_ids = response.json()["vectors"]

                # delete pincecone vectors in batches
                for i in range(0, len(vector_ids), 1000):
                    batch_ids = vector_ids[i: i + 1000]
                    st.session_state.index.delete(ids=batch_ids)

            else:
                st.error("無法刪除 Pinecone 向量！")
                return

    @staticmethod
    def generate_unique_id(content: str) -> str:
        # Ensure the content is encoded to bytes
        content_bytes = content.encode("utf-8", errors="ignore")
        # Create a SHA-256 hash object
        sha256_hash = hashlib.sha256()
        # Update the hash object with the bytes of the content
        sha256_hash.update(content_bytes)
        # Get the hexadecimal representation of the hash
        unique_id = sha256_hash.hexdigest()
        return unique_id

    @staticmethod
    def upsert_documents(documents, desc, batch_size=64):
        llm_manager = LLMManger()
        id_list = []
        total_price = 0

        for i in stqdm(range(0, len(documents), batch_size), desc=desc):
            docs = documents[i: i + batch_size]
            contents = [doc["content"] for doc in docs]
            embeddings, price = llm_manager.get_embeddings(contents)

            if embeddings is None:
                doc_name = docs[0]["name"]
                print(f"cannot encode {doc_name} page {i}-{i + batch_size}")
                continue

            total_price += price
            ids_batch = [
                PineconeManager.generate_unique_id(doc["content"])
                for doc in docs
            ]
            to_upsert = list(zip(ids_batch, embeddings, docs))
            st.session_state.index.upsert(vectors=to_upsert)
            id_list += ids_batch

        return id_list, total_price

    @staticmethod
    def fetch_document_content(vector_list):
        content = ""
        try:
            vectors = st.session_state.index.fetch(vector_list)
            metadata = [
                vector["metadata"]
                for _id, vector in vectors["vectors"].items()
            ]
            metadata = sorted(metadata, key=lambda x: x["page"])
            content = "".join([doc["content"] for doc in metadata])
        except Exception as e:
            print("Cannot fetch document content:", str(e))

        return content
