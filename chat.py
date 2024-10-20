import json
import uuid
import pandas as pd
import streamlit as st
from streamlit_gsheets import GSheetsConnection
from googleapiclient.errors import HttpError
from langchain_conversational_rag import rag
from openai import OpenAI
from datetime import datetime
from document_manager import DocumentManager

client = OpenAI(api_key=st.secrets['OPENAI_API_KEY'])
# reload messages from google sheet
st.cache_data.clear()
datetime_format = "%Y-%m-%d %H:%M:%S"
disable_chat_input = False


def get_title(message):
    prompt = f"請為接下來的訊息產生一個10字以內的標題: {message}"

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content


@st.cache_data
def transform_message_df(df, username):
    df = df[df['username'] == username]
    df = df.loc[:, df.columns != 'username']  # Drop without inplace=True

    # Ensure timestamp column is in datetime format
    df['timestamp'] = pd.to_datetime(df['timestamp'], format=datetime_format)

    # Group by chat_id and title, then sort by timestamp
    grouped = df.groupby(['chat_id', 'title'])

    # Prepare the final output
    result = []

    for (chat_id, title), group in grouped:
        messages = group[['role', 'content', 'timestamp']].sort_values(
            'timestamp').to_dict(orient='records')
        chat_entry = {
            'chat_id': chat_id,
            'title': title,
            'messages': messages
        }
        result.append(chat_entry)

    # result format:
    # [
    #     {
    #         "chat_id": "string",
    #         "title": "string",
    #         "messages": [
    #             {
    #                 "role": "string",
    #                 "content": "string",
    #                 "timestamp": "datetime"
    #             }
    #         ]
    #     }
    # ]

    sorted_result = sorted(
        result, key=lambda x: x['messages'][-1]['timestamp'], reverse=True)
    return sorted_result


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
    if "user_documents" not in st.session_state:
        st.session_state.user_documents = DocumentManager.read("userDocuments")

    if "documents" not in st.session_state:
        documents = DocumentManager.read("documents")
        if documents is None:
            st.session_state.documents = pd.DataFrame()
        else:
            st.session_state.documents = DocumentManager.get_documents_by_user(
                documents,
                st.session_state.user_documents,
                st.session_state.username
            )

    # Initialize chat history
    if "messages" not in st.session_state:
        messages = DocumentManager.read("messages")
        if messages is not None:
            st.session_state.messages = transform_message_df(
                messages, st.session_state.username)
        else:
            st.session_state.messages = []

    if "tags" not in st.session_state:
        st.session_state.tags = DocumentManager.read("tags")

options, captions = get_options_and_captions(st.session_state.messages)

if 'selected_dialog' not in st.session_state:
    st.session_state.selected_dialog = None

with st.sidebar:
    history_tab, option_tab = st.tabs(["對話紀錄", "模型選項"])

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

    new_rows = [[
        st.session_state['username'],
        str(chat_id),
        message_id,
        content,
        title,
        timestamp,
        role,
    ]]

    DocumentManager.append_rows('messages', new_rows)


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


# Accept user input
if prompt := st.chat_input("輸入你的問題", key="user_query",
                           on_submit=add_chat_history, disabled=disable_chat_input):
    document_names = st.session_state.documents["title"].tolist()
    _, stream = rag(
        prompt,
        model_id=select_model,
        tag=select_tag,
        document_names=document_names,
        session_id=st.session_state.selected_dialog,
        temperature=temp
    )

    # Display assistant response in chat message container
    with st.chat_message("assistant"):
        def generate_response():
            for chunk in stream:
                if context := chunk.get('context'):
                    for c in context:
                        print(c.metadata)

                if answer_chunk := chunk.get("answer"):
                    yield (answer_chunk)

        response = st.write_stream(generate_response)

    chat_id = update_chat_history(response, 'assistant')
    title = st.session_state.selected_dialog
    add_message_to_database(
        title, chat_id, st.session_state.user_query, 'user')
    add_message_to_database(title, chat_id, response, 'assistant')
