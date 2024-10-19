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
from stqdm import stqdm
from time import sleep
from document_manager import DocumentManager

openai_client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
pc = Pinecone(api_key=st.secrets["PINECONE_API_KEY"])

with st.spinner("讀取資料中..."):
    if "user_documents" not in st.session_state:
        st.session_state.user_documents = DocumentManager.read("userDocuments")

    if "documents" not in st.session_state:
        documents = DocumentManager.read("documents")
        st.session_state.documents = DocumentManager.get_documents_by_user(
            documents,
            st.session_state.user_documents,
            st.session_state.username
        )

if "upload_failure" in st.session_state:
    if len(st.session_state.upload_failure) == 0:
        st.toast("資料上傳成功！", icon="✅")
    else:
        for doc in st.session_state.upload_failure:
            st.toast(f"無法上傳文件「{doc}」，請稍後再試", icon="❌")

    st.session_state.pop("upload_failure")

# if "upload_success" in st.session_state and st.session_state.upload_success:
#     st.toast("資料上傳成功！", icon="✅")
#     st.session_state.upload_success = 0

if "delete_success" in st.session_state and st.session_state.delete_success:
    st.toast("資料刪除成功！", icon="✅")
    st.session_state.delete_success = 0


def delete_pinecone_documents(index):
    selected_indices = event.selection.rows
    selected_document_ids = st.session_state.documents.loc[
        selected_indices, "document_id"
    ].tolist()
    vectors = DocumentManager.read("vectors")
    filtered_df = vectors[vectors["document_id"].isin(selected_document_ids)]
    vector_ids = filtered_df["vector_id"].tolist()

    for i in range(0, len(vector_ids), 1000):
        batch_ids = vector_ids[i: i + 1000]
        index.delete(ids=batch_ids)


@st.dialog("刪除文件")
def delete_documents(my_documents):
    selected_indices = event.selection.rows
    titles = my_documents.loc[selected_indices, "title"].tolist()
    title_str = "\n".join([f"- {title}" for title in titles])
    info_str = "確認刪除以下文件？\n" + title_str
    st.markdown(info_str)

    if st.button("確認"):
        index = get_index(st.secrets["INDEX_NAME"])
        with st.spinner(text="刪除文件中..."):
            delete_pinecone_documents(index)

            # update sheet "vectors"
            vectors = DocumentManager.read("vectors")
            selected_document_ids = my_documents.loc[
                selected_indices, "document_id"
            ].tolist()
            row_indices = vectors.index[
                vectors["document_id"].isin(selected_document_ids)
            ].tolist()
            DocumentManager.delete_rows("vectors", row_indices)

            # update sheet "documents"
            documents = DocumentManager.read("documents")
            row_indices = documents.index[
                documents["document_id"].isin(selected_document_ids)
            ].tolist()
            DocumentManager.delete_rows("documents", row_indices)

            filtered_documents = st.session_state.documents[
                ~st.session_state.documents["document_id"].isin(
                    selected_document_ids
                )
            ]
            filtered_documents = filtered_documents.reset_index(drop=True)
            st.session_state.documents = filtered_documents

            # update sheet "userDocuments"
            user_doc = DocumentManager.read("userDocuments")
            username = st.session_state.username
            row_indices = user_doc.index[
                (user_doc["document_id"].isin(selected_document_ids))
            ]
            DocumentManager.delete_rows("userDocuments", row_indices)

            filtered_user_documents = user_doc[
                ~(user_doc["document_id"].isin(selected_document_ids))
            ].reset_index(drop=True)
            st.session_state.user_documents = filtered_user_documents

        st.session_state.delete_success = 1
        st.rerun()


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


def upload_document_to_google_sheet(id_list, title, tag):
    document_id = str(uuid.uuid4())
    new_document_row = [{
        "document_id": document_id,
        "title": title,
        "tag": tag,
    }]

    new_user_document_row = [{
        "id": str(uuid.uuid4()),
        "username": st.session_state["username"],
        "document_id": document_id,
        "access_level": "write",
    }]

    new_vectors = [[document_id, vector_id] for vector_id in id_list]

    try:
        # update sheet "documents"
        DocumentManager.append_rows(
            "documents", [list(new_document_row[0].values())])

        # update sheet "userDocuments"
        DocumentManager.append_rows(
            "userDocuments", [list(new_user_document_row[0].values())])

        # update sheet "vectors"
        DocumentManager.append_rows("vectors", new_vectors)
    except:
        raise

    # update local data
    new_df = pd.DataFrame(new_document_row)
    new_df = pd.concat([st.session_state.documents, new_df])
    new_df = new_df.reset_index(drop=True)
    st.session_state.documents = new_df

    new_df = pd.DataFrame(new_user_document_row)
    new_df = pd.concat([st.session_state.user_documents, new_df])
    new_df = new_df.reset_index(drop=True)
    st.session_state.user_documents = new_df


@st.dialog("上傳文件")
def upload_document():
    options = st.secrets["TAG_OPTION"][:]
    if "全" in options:
        options.remove("全")

    uploaded_files = st.file_uploader(
        "選取檔案", accept_multiple_files=True, type="pdf")
    tag = st.selectbox("選取文件類別", options)

    # check if the document already exists in the database
    titles = [Path(file.name).stem for file in uploaded_files]
    matching_titles = st.session_state.documents[
        st.session_state.documents["title"].isin(titles)
    ]["title"].tolist()

    if len(matching_titles) != 0:
        st.error(f"「{matching_titles[0]}」已經在資料庫中！")

    disabled = (len(matching_titles) != 0) or (len(uploaded_files) == 0)

    if st.button("提交", disabled=disabled, key="submit_button"):
        progress_text = "上傳文件..."
        index = get_index(st.secrets["INDEX_NAME"])
        titles, vector_list = [], []

        st.session_state.upload_failure = []
        for i, uploaded_file in enumerate(uploaded_files):
            title = Path(uploaded_file.name).stem
            bytes_data = uploaded_file.getvalue()

            try:
                # Update pinecone index
                desc = f"讀取第 {i+1}  /  {len(uploaded_files)} 文件"
                data = load_pdf(bytes_data, tag, title, desc)
                desc = f"計算第 {i+1}  /  {len(uploaded_files)} 文件特徵向量"
                id_list = upsert_documents(index, data, desc)

                titles.append(title)
                vector_list.append(id_list)
            except:
                st.session_state.upload_failure.append(title)

        # update data on Google sheet
        for i in stqdm(range(len(titles)), desc="同步至資料庫"):
            try:
                upload_document_to_google_sheet(vector_list[i], titles[i], tag)
            except:
                st.session_state.upload_failure.append(titles[i])

        # st.session_state.upload_success = 1
        st.rerun()


@st.cache_data
def get_documents_by_permission(documents, user_documents):
    df = user_documents[
        (user_documents["username"] == st.session_state.username)
    ]

    my_document_ids = df[
        df["access_level"] == "write"
    ]["document_id"].tolist()
    shared_document_ids = df[
        df["access_level"] == "read"
    ]["document_id"].tolist()

    my_documents = documents[
        documents["document_id"].isin(my_document_ids)
    ].reset_index(drop=True)
    shared_documents = documents[
        documents["document_id"].isin(shared_document_ids)
    ].reset_index(drop=True)

    return my_documents, shared_documents


column_configuration = {
    "document_id": None,
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
if st.session_state.documents is None or st.session_state.user_documents is None:
    st.error("無法讀取資料，請稍候並重新整理")
else:
    my_document_tab, shared_document_tab = st.tabs(["我的文件", "共用文件"])
    my_documents, shared_documents = get_documents_by_permission(
        st.session_state.documents, st.session_state.user_documents
    )

    with my_document_tab:
        event = st.dataframe(
            my_documents,
            column_config=column_configuration,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="multi-row",
        )

        columns = st.columns([1] * 9)
        with columns[0]:
            st.button(label="上傳", on_click=upload_document,
                      key="upload_button")

        with columns[1]:
            disabled = not bool(event.selection.rows)
            st.button(
                "刪除",
                type="primary",
                on_click=delete_documents,
                args=(my_documents, ),
                disabled=disabled,
                key="delete_button"
            )

    with shared_document_tab:
        st.dataframe(
            shared_documents,
            column_config=column_configuration,
            use_container_width=True,
            hide_index=True,
            on_select="ignore"
        )
