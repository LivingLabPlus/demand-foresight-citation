import json
import uuid
import streamlit as st
from langchain_conversational_rag import rag


# Initialize chat history
if "messages" not in st.session_state:
    with open('data/conversations.json') as f:
        st.session_state.messages = json.load(f)

    options, captions = [], []
    for m in st.session_state.messages:
        options.append(m['chat_id'])
        captions.append(m['title'])

    st.session_state.options = options
    st.session_state.captions = captions


with st.sidebar:
    history_tab, option_tab = st.tabs(["對話紀錄", "模型選項"])

    with option_tab:
        select_model = st.selectbox(
            label="模型", 
            options=["gpt-4o", "claude-3-opus-20240229"], 
            index=0, 
            key="model_selection"
        )
        select_tag = st.selectbox(
            label="文件類別", 
            options=["全", "AI", "能源", "樂齡", "智慧城市"], 
            index=0, 
            key="tag_selection"
        )
        temp = st.slider("Temperature", min_value=0.00 , max_value=1.0, step=0.01, key="temperature")

    with history_tab:
        def new_chat():
            st.session_state.selected_dialog = None

        st.button(
            "新對話", 
            on_click=new_chat,
            use_container_width=True
        )

        selected_dialog = st.radio(
            "對話紀錄",
            st.session_state.options,
            label_visibility="collapsed",
            captions=st.session_state.captions,
            index=None,
            key='selected_dialog'
        )

# display selected dialogue
if st.session_state.selected_dialog is not None:
    chat_id = st.session_state.selected_dialog
    print('chat id:', chat_id)
    
    for dialog in st.session_state.messages:
        if dialog['chat_id'] != chat_id:
            continue
    
        print('messages:', dialog['messages'])

        for message in dialog['messages']:                
            with st.chat_message(message['role']):
                st.markdown(message['content'])


def update_chat_history(response, role):
    chat_id = st.session_state.selected_dialog
    for dialog in st.session_state.messages:
        if dialog['chat_id'] != chat_id:
            continue
        dialog['messages'].append({
            'role': role,
            'content': response
        })


def add_chat_history():
    # a new dialogue
    if st.session_state.selected_dialog is None:
        # Add user message to chat history
        chat_id = str(uuid.uuid4())[:6]
        dialog = {
            'chat_id': chat_id,
            'title': prompt,
            'messages': [
                {
                    'role': 'user',
                    'content': st.session_state.user_query
                }
            ]
        }
        st.session_state.messages.append(dialog)
        st.session_state.options.insert(0, chat_id)
        st.session_state.captions.insert(0, st.session_state.user_query)
        st.session_state.selected_dialog = chat_id
    else:
        update_chat_history(st.session_state.user_query, 'user')


# Accept user input
if prompt := st.chat_input("輸入你的問題", key="user_query", on_submit=add_chat_history):
    _, stream = rag(
        prompt,
        model_id=select_model,
        tag=select_tag, 
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
                    yield(answer_chunk)

        response = st.write_stream(generate_response)
        
    update_chat_history(response, 'assistant')