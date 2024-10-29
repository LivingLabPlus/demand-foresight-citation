import io
import uuid
import hashlib
import PyPDF2
import pandas as pd
import streamlit as st
from streamlit_gsheets import GSheetsConnection
from pinecone import Pinecone, ServerlessSpec
from pathlib import Path
from openai import OpenAI
from tqdm import tqdm
from time import sleep
from stqdm import stqdm
from sqlalchemy.sql import text

st.set_page_config(page_title="資料庫管理")

openai_client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
conn = st.connection('pinecone_db', type='sql')

with st.spinner("讀取資料中..."):
    if "documents" not in st.session_state:
        st.session_state.documents = conn.query(
            'select * from documents', ttl=5)

if "upload_success" in st.session_state and st.session_state.upload_success:
    st.toast("資料上傳成功！", icon="✅")
    st.session_state.upload_success = 0


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


@st.cache_resource
def get_index(index_name):
    pc = Pinecone(api_key=st.secrets['PINECONE_API_KEY'])
    index = pc.Index(index_name)
    return index


def load_pdf(bytes_data, tag, name, desc):
    p = io.BytesIO(bytes_data)
    reader = PyPDF2.PdfReader(p)
    data = []

    for i in stqdm(range(len(reader.pages)), desc=desc):
        content = reader.pages[i].extract_text()
        clean_content = content.encode('utf-8', 'replace').decode('utf-8')

        if len(content) < 10:
            continue

        data.append({
            "tag": tag,
            "name": name,
            "page": i + 1,
            "content": clean_content,
        })

    return data


def get_embeddings(texts, model="text-embedding-3-small"):
    embeddings = openai_client.embeddings.create(input=texts, model=model)
    embeddings = [d.embedding for d in embeddings.data]
    return embeddings


def upsert_documents(index, documents, desc, batch_size=64):
    id_list = []
    for i in stqdm(range(0, len(documents), batch_size), desc=desc):
        docs = documents[i: i + batch_size]
        contents = [doc["content"] for doc in docs]
        embeddings = get_embeddings(contents)

        if embeddings is None:
            doc_name = docs[0]["name"]
            print(f"cannot encode {doc_name} page {i}-{i + batch_size}")
            continue

        ids_batch = [generate_unique_id(doc["content"]) for doc in docs]
        to_upsert = list(zip(ids_batch, embeddings, docs))
        index.upsert(vectors=to_upsert)
        id_list += ids_batch
    return id_list


@st.dialog("上傳文件")
def upload_document():
    uploaded_files = st.file_uploader(
        "選取檔案", accept_multiple_files=True, type="pdf")
    index_name = st.selectbox(
        "Pinecone 資料庫名稱",
        st.secrets["PINECONE_INDICES"],
        key="in_dialog_index_name_selectbox"
    )
    tag = st.selectbox(
        "文件類別",
        st.secrets["index"][index_name]["tag_options"],
        key="in_dialog_tag_selectbox"
    )

    titles = [Path(file.name).stem for file in uploaded_files]
    matching_titles = st.session_state.documents[
        st.session_state.documents["title"].isin(titles)
    ]["title"].tolist()

    if len(matching_titles) != 0:
        st.error(f"「{matching_titles[0]}」已經在資料庫中！")

    disabled = (len(matching_titles) != 0) or (len(uploaded_files) == 0)

    if st.button("提交", disabled=disabled, key="submit_button"):

        current_stage = 0
        total_stage = len(uploaded_files) * 3
        index = get_index(index_name)

        with conn.session as s:
            for i, uploaded_file in enumerate(uploaded_files):
                title = Path(uploaded_file.name).stem
                bytes_data = uploaded_file.getvalue()

                # Update pinecone index
                desc = f"讀取第 {i+1}  /  {len(uploaded_files)} 文件"
                data = load_pdf(bytes_data, tag, title, desc)
                desc = f"計算第 {i+1}  /  {len(uploaded_files)} 文件特徵向量"
                upsert_documents(index, data, desc)

                # Update in memory documents
                new_row = [{"index_name": index_name,
                           "title": title, "tag": tag}]
                new_df = pd.DataFrame(new_row)
                new_df = pd.concat([st.session_state.documents, new_df])
                new_df = new_df.reset_index(drop=True)
                st.session_state.documents = new_df

                # Update local storage
                s.execute(text("INSERT INTO documents (index_name, title, tag) VALUES (:index_name, :title, :tag);"),
                          params=dict(index_name=index_name, title=title, tag=tag))

            s.commit()

        st.session_state.upload_success = 1
        st.rerun()


@st.cache_data
def get_documents_by_index_name(documents, selected_index, selected_tag):
    df = documents[(documents["index_name"] == selected_index)
                   & (documents["tag"] == selected_tag)]
    df = df[["title", "tag"]]
    return df.reset_index(drop=True)


column_configuration = {
    "title": st.column_config.TextColumn(
        "文件名稱", help="文件名稱", max_chars=1024, width="large"
    ),
    "tag": st.column_config.TextColumn(
        "標籤",
        help="文件類別",
        width="small",
    ),
}

st.header("資料庫")
selected_index = st.selectbox(
    "資料庫名稱",
    st.secrets["PINECONE_INDICES"],
    key="homepage_index_name_selectbox"
)
selected_tag = st.selectbox(
    "文件類別",
    st.secrets["index"][selected_index]["tag_options"],
    key="homepage_tag_selectbox"
)

my_documents = get_documents_by_index_name(
    st.session_state.documents, selected_index, selected_tag
)

event = st.dataframe(
    my_documents,
    column_config=column_configuration,
    use_container_width=True,
    hide_index=True,
    on_select="rerun",
    selection_mode="multi-row",
)
st.button(label="上傳", on_click=upload_document, key="upload_button")
