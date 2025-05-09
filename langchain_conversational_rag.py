from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.prompts import MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain.chains import create_history_aware_retriever
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_anthropic import ChatAnthropic
from langchain_pinecone import PineconeVectorStore
from langchain import hub
from pinecone import Pinecone, ServerlessSpec
import streamlit as st
import uuid

# Import required dependencies 
from typing import Any, Dict, List, Optional, Union, Protocol

# Define mock classes for required types
class BaseCache(Protocol):
    pass

class BaseCallbacks(Protocol):
    pass

system_prompt = '''You are a helpful assistant that is an expert at answering questions with citations.

Here are the documents:
<documents>
{context}
</documents>

When a user asks a question, perform the following tasks:
1. Find the quotes from the documents that are the most relevant to answering the question. These quotes can be quite long if necessary. You may need to use many quotes to answer a single question.
2. Assign numbers to these quotes in the order they were found. Each segment of the documentation should only be assigned a number once.
3. Based on the document and quotes, answer the question. If no relevant documents are found, answer "資料庫中找不到相關資料".
4. When answering the question, provide citations references in square brackets containing the number generated in step 2 (the number the citation was found)
5. Answer in "traditional Chinese", and structure the output in this concise markdown format:
```
Answer with citations [1][2]

## Sources
1. <Source1>, p.<page>
2. <Source2>, p.<page>
...
```
Replace <Source1>, <Source2>, etc., with the actual source names, and <page> with the relevant page numbers if available.
'''
contextualize_q_system_prompt = (
    "Given a chat history and the latest user question "
    "which might reference context in the chat history, "
    "formulate a standalone question which can be understood "
    "without the chat history. Do NOT answer the question, "
    "just reformulate it if needed and otherwise return it as is."
)


def get_index(index_name):
    pc = Pinecone(api_key=st.secrets['PINECONE_API_KEY'])
    index = pc.Index(index_name)
    return index


def get_retriever(index_name, document_names):
    model_name = 'text-embedding-3-small'
    embeddings = OpenAIEmbeddings(model=model_name)

    index = get_index(index_name)
    text_field = "content"
    vectorstore = PineconeVectorStore(
        index, embeddings, text_field
    )

    search_kwargs = {
        "k": st.secrets.rag.top_k,
        "filter": {
            "name": {
                "$in": document_names
            }
        }
    }

    retriever = vectorstore.as_retriever(search_kwargs=search_kwargs)
    return retriever


# Formatting search results
def format_docs(docs):
    result = []
    for doc in docs:
        name = doc.metadata['name']
        page = doc.metadata['page']
        content = doc.page_content
        # result.append(f'<item name="{name}" page="{page}">\n<page_content>\n{content}\n</page_content>\n</item>')
        # Shortened format, keeping only essential information
        result.append(f'<item name="{name}" page="{page}">{content}</item>')

    return '\n'.join(result)


def get_rag_chain(
    model_id,
    document_names,
    temperature=0,
    index_name='demand-foresight'
):
    retriever = get_retriever(index_name, document_names)
    if 'gpt' in model_id:
        llm = ChatOpenAI(
            model=model_id,
            temperature=temperature,
            max_tokens=16384,
            model_kwargs={"stream_options": {"include_usage": True}},
            api_key=st.secrets['OPENAI_API_KEY'],
        )
    elif 'claude' in model_id:
        llm = ChatAnthropic(
            model=model_id,
            temperature=temperature,
            max_tokens=8192,
            stream_usage=True,
            api_key=st.secrets['ANTHROPIC_API_KEY']
        )

    contextualize_q_prompt = hub.pull(
        st.secrets.prompts.rag_contextualize_q_system_prompt,
        api_key=st.secrets.LANGCHAIN_API_KEY
    )

    history_aware_retriever = create_history_aware_retriever(
        llm, retriever, contextualize_q_prompt
    )

    prompt = hub.pull(
        st.secrets.prompts.rag_system_prompt,
        api_key=st.secrets.LANGCHAIN_API_KEY
    )

    chain = (
        RunnablePassthrough.assign(
            context=(lambda x: format_docs(x["context"])))
        | prompt
        | llm
        | StrOutputParser()
    )

    rag_chain = RunnablePassthrough.assign(context=history_aware_retriever).assign(
        answer=chain
    )
    return rag_chain


def get_session_history(session_id):
    return SQLChatMessageHistory(session_id, "sqlite:///memory.db")


def rag(
    question,
    model_id,
    document_names,
    session_id=None,
    temperature=0
):
    rag_chain = get_rag_chain(
        model_id,
        document_names,
        temperature=temperature,
        index_name=st.secrets['INDEX_NAME']
    )
    conversational_rag_chain = RunnableWithMessageHistory(
        rag_chain,
        get_session_history,
        input_messages_key="input",
        history_messages_key="chat_history",
        output_messages_key="answer",
    )

    if session_id is None:
        session_id = str(uuid.uuid4())

    stream = conversational_rag_chain.stream(
        {"input": question},
        config={"configurable": {"session_id": session_id}},
    )

    return session_id, stream


if __name__ == '__main__':
    model_id = "claude-3-opus-20240229"
    tag = 'AI'
    question = '哪一個機關負責老人狀況調查'
    temperature = 0
    session_id, stream = rag(
        question,
        model_id,
        tag=tag,
        temperature=temperature
    )

    for chunk in stream:
        if answer_chunk := chunk.get("answer"):
            print(answer_chunk, end='', flush=True)
    print()

    question = '多久要進行一次？'
    _, stream = rag(
        question,
        model_id,
        tag=tag,
        session_id=session_id,
        temperature=temperature
    )
    for chunk in stream:
        if answer_chunk := chunk.get("answer"):
            print(answer_chunk, end='', flush=True)
    print()
