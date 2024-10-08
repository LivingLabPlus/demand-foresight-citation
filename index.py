import streamlit as st
from langchain_conversational_rag import rag

st.set_page_config(page_title=st.secrets["PAGE_TITLE"])

select_model = st.sidebar.selectbox(
    label="模型", 
    options=st.secrets['MODEL_OPTION'],
    index=0, 
    key="model_selection"
)
select_tag = st.sidebar.selectbox(
    label="文件類別",  
    options=st.secrets['TAG_OPTION'],
    index=0, 
    key="tag_selection"
)
temp = st.sidebar.slider("Temperature", min_value=0.00 , max_value=1.0, step=0.01, key="temperature")
st.sidebar.link_button("測試回饋表單", st.secrets["SHEET_LINK"])

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Accept user input
if prompt := st.chat_input("輸入你的問題"):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(prompt)

    session_id = None
    if "session_id" in st.session_state:
        session_id = st.session_state.session_id

    if session_id is not None:
        _, stream = rag(
            prompt,
            model_id=select_model,
            tag=select_tag,
            session_id=session_id, 
            temperature=temp
        )
    else:
        session_id, stream = rag(
            prompt,
            model_id=select_model,
            tag=select_tag, 
            temperature=temp
        )
        st.session_state.session_id = session_id

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
        
    st.session_state.messages.append({"role": "assistant", "content": response})