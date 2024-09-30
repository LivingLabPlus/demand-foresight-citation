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

openai_client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
pc = Pinecone(api_key=st.secrets["PINECONE_API_KEY"])

@st.cache_data
def display_documents(df):
    return df[["title", "tag"]]

@st.cache_data
def filter_df_by_username(df):
    return df[df["username"] == st.session_state.username]

@st.cache_data
def filter_df_by_document_ids(df, document_ids):
    return df[df["document_id"].isin(document_ids)]


if "conn" not in st.session_state:
    # Create a connection object.
    conn = st.connection("gsheets", type=GSheetsConnection)
    st.session_state.conn = conn

if "user_documents" not in st.session_state:
    st.session_state.user_documents = st.session_state.conn.read(worksheet="userDocuments")

user_user_documents = filter_df_by_username(st.session_state.user_documents)
document_ids = user_user_documents["document_id"].tolist()
if "documents" not in st.session_state:
    st.session_state.documents = st.session_state.conn.read(worksheet="documents")

if "vectors" not in st.session_state:
    st.session_state.vectors = st.session_state.conn.read(worksheet="vectors")

if "upload_success" in st.session_state and st.session_state.upload_success:
    st.toast("資料上傳成功！", icon="✅")
    st.session_state.upload_success = 0

if "delete_success" in st.session_state and st.session_state.delete_success:
    st.toast("資料刪除成功！", icon="✅")
    st.session_state.delete_success = 0


column_configuration = {
    "title": st.column_config.TextColumn(
        "文件名稱", help="文件名稱", max_chars=1024, width="large"
    ),
    "tag": st.column_config.SelectboxColumn(
        "標籤",
        help="文件類別",
        width="small",
        options=[
            "AI",
            "能源",
        ],
        required=True
    ),
}

st.header("資料庫")
user_documents = filter_df_by_document_ids(st.session_state.documents, document_ids)
displayed_documents = display_documents(user_documents)
event = st.dataframe(
    displayed_documents,
    column_config=column_configuration,
    use_container_width=True,
    hide_index=True,
    on_select="rerun",
    selection_mode="multi-row",
)


def delete_pinecone_documents(index):
    selected_indices = event.selection.rows
    selected_document_ids = st.session_state.documents.loc[selected_indices, "document_id"].tolist()
    filtered_df = st.session_state.vectors[
        st.session_state.vectors["document_id"].isin(selected_document_ids)
    ]
    vector_ids = filtered_df["vector_id"].tolist()
    
    for i in range(0, len(vector_ids), 1000):
        batch_ids = vector_ids[i : i + 1000]
        index.delete(ids=batch_ids)

    new_vectors_df = st.session_state.vectors[
        ~st.session_state.vectors["document_id"].isin(selected_document_ids)
    ]
    st.session_state.conn.update(worksheet="vectors", data=new_vectors_df)
    st.session_state.vectors = new_vectors_df


@st.dialog("刪除文件")
def delete_documents():
    selected_indices = event.selection.rows
    titles = st.session_state.documents.loc[selected_indices, "title"].tolist()
    title_str = "\n".join([f"- {title}" for title in titles])
    info_str = "確認刪除以下文件？\n" + title_str
    st.markdown(info_str)

    if st.button("確認"):
        index = get_index(st.secrets["INDEX_NAME"])
        with st.spinner(text="刪除中..."):    
            delete_pinecone_documents(index)
            filtered_documents = st.session_state.documents.drop(selected_indices)
            filtered_documents = filtered_documents.reset_index(drop=True)
            st.session_state.conn.update(worksheet="documents", data=filtered_documents)

            document_ids = st.session_state.documents.loc[selected_indices, "document_id"].tolist()
            username = st.session_state.username
            user_doc = st.session_state.user_documents
            filtered_user_documents = user_doc[~((user_doc["username"] == username) & (user_doc["document_id"].isin(document_ids)))]
            st.session_state.conn.update(worksheet="userDocuments", data=filtered_user_documents)

        st.session_state.documents = filtered_documents
        st.session_state.user_documents = filtered_user_documents
        st.session_state.delete_success = 1
        st.rerun()


def generate_unique_id(content: str) -> str:
    # Ensure the content is encoded to bytes
    content_bytes = content.encode("utf-8")
    # Create a SHA-256 hash object
    sha256_hash = hashlib.sha256()
    # Update the hash object with the bytes of the content
    sha256_hash.update(content_bytes)
    # Get the hexadecimal representation of the hash
    unique_id = sha256_hash.hexdigest()
    return unique_id


@st.cache_resource
def get_index(index_name):
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


def load_pdf(bytes_data, tag, name):
    p = io.BytesIO(bytes_data)
    reader = PyPDF2.PdfReader(p)
    data = []

    for i in range(len(reader.pages)):
        content = reader.pages[i].extract_text()

        if len(content) < 10:
            continue

        data.append({
            "tag": tag,
            "name": name,
            "page": i + 1,
            "content": content,
        })

    return data


def get_embeddings(texts, model="text-embedding-3-small"):
    embeddings = openai_client.embeddings.create(input=texts, model=model)
    embeddings = [d.embedding for d in embeddings.data]
    return embeddings


def upsert_documents(index, documents, batch_size=64):
    id_list = []
    for i in tqdm(range(0, len(documents), batch_size)):
        docs = documents[i : i + batch_size]
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


def upload_document_to_google_sheet(id_list, title, tag):
    # update local data
    document_id = str(uuid.uuid4())
    new_row = [{
        "document_id": document_id,
        "title": title,
        "tag": tag,
    }]
    new_df = pd.DataFrame(new_row)
    new_df = pd.concat([st.session_state.documents, new_df])
    new_df = new_df.reset_index(drop=True)
    st.session_state.documents = new_df

    # update sheet "documents" 
    st.session_state.conn.update(worksheet="documents", data=new_df)

    new_vectors = [{
        "document_id": document_id,
        "vector_id": vector_id
    } for vector_id in id_list]
    new_df = pd.DataFrame(new_vectors)
    new_df = pd.concat([st.session_state.vectors, new_df])
    new_df = new_df.reset_index(drop=True)
    st.session_state.vectors = new_df

    # update sheet "vectors"
    st.session_state.conn.update(worksheet="vectors", data=new_df)

    new_row = [{
        "id": str(uuid.uuid4()),
        "username": st.session_state["username"],
        "document_id": document_id,	
        "access_level": "write",
    }]
    new_df = pd.DataFrame(new_row)
    new_df = pd.concat([st.session_state.user_documents, new_df])
    new_df = new_df.reset_index(drop=True)
    st.session_state.user_documents = new_df

    # update sheet "userDocuments" 
    st.session_state.conn.update(worksheet="userDocuments", data=new_df)


@st.dialog("上傳文件")
def upload_document():
    options = st.secrets["TAG_OPTION"][:]
    if "全" in options:
        options.remove("全")

    uploaded_files = st.file_uploader("選取檔案", accept_multiple_files=True, type="pdf")
    tag = st.selectbox("選取文件類別", options)

    titles = [Path(file.name).stem for file in uploaded_files]
    matching_titles = displayed_documents[
        displayed_documents["title"].isin(titles)
    ]["title"].tolist()
    
    if len(matching_titles) != 0:
        st.error(f"「{matching_titles[0]}」已經在資料庫中！")
    
    disabled = (len(matching_titles) != 0) or (len(uploaded_files) == 0)

    if st.button("提交", disabled=disabled, key="submit_button"):
        progress_text = "上傳文件..."
        my_bar = st.progress(0, text=progress_text)
        current_stage = 0
        total_stage = len(uploaded_files) * 3
        index = get_index(st.secrets["INDEX_NAME"])

        for i, uploaded_file in enumerate(uploaded_files):
            title = Path(uploaded_file.name).stem
            bytes_data = uploaded_file.getvalue()
            
            data = load_pdf(bytes_data, tag, title)
            
            current_stage += 1
            my_bar.progress(current_stage / total_stage, text=progress_text)
            id_list = upsert_documents(index, data)
            
            # update data on Google sheet
            current_stage += 1
            my_bar.progress(current_stage / total_stage, text=progress_text)
            upload_document_to_google_sheet(id_list, title, tag)
            
            current_stage += 1
            my_bar.progress(current_stage / total_stage, text=progress_text)

        my_bar.empty()
        # st.session_state.displayed_documents = display_documents(st.session_state.documents)
        st.session_state.upload_success = 1
        st.rerun()


columns = st.columns([1] * 9)
with columns[0]:
    st.button(label="上傳", on_click=upload_document, key="upload_button")

with columns[1]:
    disabled = not bool(event.selection.rows)
    st.button(
        "刪除", 
        type="primary", 
        on_click=delete_documents,
        disabled=disabled,
        key="delete_button"
    )
