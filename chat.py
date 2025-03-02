import json
import uuid
import requests
import pandas as pd
import streamlit as st
from streamlit_gsheets import GSheetsConnection
from googleapiclient.errors import HttpError
from langchain_conversational_rag import rag
from openai import OpenAI
from datetime import datetime
from langchain_community.callbacks import get_openai_callback

from managers import DocumentManager, SessionManager, CostManager

client = OpenAI(api_key=st.secrets['OPENAI_API_KEY'])
# reload messages from google sheet
st.cache_data.clear()
datetime_format = "%Y-%m-%d %H:%M:%S"
disable_chat_input = False


def title_exists(title):
    for dialog in st.session_state.messages:
        if dialog["title"] == title:
            return True
    return False


def get_title(message):
    prompt = f"請為接下來的訊息產生一個10字以內的標題: {message}"

    while True:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ]
        )
        title = response.choices[0].message.content
        if not title_exists(title):
            return title


@st.cache_data
def get_options_and_captions(messages):
    options, captions = [], []
    sorted_messages = sorted(
        messages, key=lambda x: x['messages'][-1]['timestamp'], reverse=True)

    for m in sorted_messages:
        options.append(m['title'])
        # retrieve the timestamp of the first message in the conversion
        captions.append(m['messages'][-1]['timestamp'].strftime("%Y-%m-%d"))

    return options, captions


if (("user_documents" in st.session_state and st.session_state.user_documents is None)
        or ("documents" in st.session_state and st.session_state.documents is None)):
    st.error("無法讀取資料，請稍候並重新整理")
    disable_chat_input = True

with st.spinner("讀取資料中..."):
    SessionManager.load_initial_data()

options, captions = get_options_and_captions(st.session_state.messages)

if 'selected_dialog' not in st.session_state:
    st.session_state.selected_dialog = None

with st.sidebar:
    option_tab, history_tab = st.tabs(["對話選項", "對話紀錄"])

    with option_tab:
        select_model = st.selectbox(
            label="模型",
            options=st.secrets["MODEL_OPTION"],
            index=0,
            key="model_selection"
        )
        select_tag = st.selectbox(
            label="文件類別",
            options=st.session_state.tags["tag"].tolist(),
            index=0,
            key="tag_selection"
        )

        select_documents = None
        document_options = st.session_state.documents[
            st.session_state.documents["tag"] == select_tag
        ]["title"].tolist()

        # allow users to specify which documents to use in the conversation
        if st.secrets["modules"]["doc_chat"]:
            select_documents = st.multiselect(
                label="文件名稱（未選取則搜尋全部文件）",
                options=document_options,
                placeholder="選取對話文件",
                key="document_selection"
            )

        temp = st.slider("Temperature", min_value=0.00,
                         max_value=1.0, step=0.01, key="temperature")

    with history_tab:
        def new_chat():
            st.session_state.selected_dialog = None

        st.button(
            "新對話",
            on_click=new_chat,
            use_container_width=True
        )

        if len(options) != 0:
            selected_dialog = st.radio(
                "對話紀錄",
                options,
                captions=captions,
                label_visibility="collapsed",
                key='selected_dialog'
            )

# display selected dialogue
if st.session_state.selected_dialog is not None:
    title = st.session_state.selected_dialog

    for dialog in st.session_state.messages:
        if dialog['title'] != title:
            continue

        for message in dialog['messages']:
            with st.chat_message(message['role']):
                st.markdown(message['content'])


def add_message_to_database(title, chat_id, content, role):
    message_id = str(uuid.uuid4())
    timestamp = datetime.now().strftime(datetime_format)

    api_url = f"{st.secrets.BACKEND_URL}/messages"
    new_message = {
        "username": st.session_state.username,
        "chat_id": str(chat_id),
        "message_id": message_id,
        "content": content,
        "title": title,
        "timestamp": timestamp,
        "role": role
    }
    response = requests.post(api_url, json=new_message)
    if response.status_code != 200:
        st.error("新增訊息發生錯誤！")


def update_chat_history(response, role):
    title = st.session_state.selected_dialog
    for dialog in st.session_state.messages:
        if dialog['title'] != title:
            continue

        dialog['messages'].append({
            'role': role,
            'content': response,
            'timestamp': datetime.now()
        })
        return dialog['chat_id']

    return None


def add_chat_history():
    # a new dialogue
    if st.session_state.selected_dialog is None:
        # Add user message to chat history
        title = get_title(st.session_state.user_query)
        chat_id = uuid.uuid4()
        st.session_state.selected_dialog = title
        dialog = {
            'chat_id': chat_id,
            'title': title,
            'messages': [{
                'role': 'user',
                'content': st.session_state.user_query,
                'timestamp': datetime.now()
            }]
        }
        st.session_state.messages.append(dialog)
    else:
        update_chat_history(st.session_state.user_query, 'user')


def calculate_cost(prompt_tokens, completion_tokens):
    return (3 * prompt_tokens + 15 * completion_tokens) / 1e6


# Accept user input
if prompt := st.chat_input("輸入你的問題", key="user_query",
                           on_submit=add_chat_history, disabled=disable_chat_input):
    # if no documents are selected, pass all documents with tag "select_tag" to rag
    if select_documents is None or len(select_documents) == 0:
        document_names = document_options
    else:
        document_names = select_documents

    _, stream = rag(
        prompt,
        model_id=select_model,
        document_names=document_names,
        session_id=st.session_state.selected_dialog,
        temperature=temp
    )

    # Display assistant response in chat message container
    with st.chat_message("assistant"):
        def generate_response():
            with get_openai_callback() as cb:
                for chunk in stream:
                    if answer_chunk := chunk.get("answer"):
                        yield (answer_chunk)

                if "gpt" in select_model:
                    total_cost = cb.total_cost
                else:
                    # calculate pricing for anthropic model
                    total_cost = CostManager.calculate_cost(
                        cb.prompt_tokens,
                        cb.completion_tokens,
                        select_model
                    )

                CostManager.update_cost(total_cost)

        response = st.write_stream(generate_response)

    chat_id = update_chat_history(response, 'assistant')
    title = st.session_state.selected_dialog
    add_message_to_database(
        title, chat_id, st.session_state.user_query, 'user')
    add_message_to_database(title, chat_id, response, 'assistant')
