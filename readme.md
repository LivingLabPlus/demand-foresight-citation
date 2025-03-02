# Demand Forsight Streamlit Application

### Page Files

These files define the primary pages of the Streamlit app and their respective functionalities:

- **`index.py`**:  
  The main entry point for the application. It sets up page configurations, manages authentication, and dynamically loads pages based on module settings in the app’s configuration.

- **`account.py`**:  
  Provides account management features. Users can view their usernames, reset passwords, and log out.

- **`admin.py`**:  
  An admin-only interface for managing document access permissions. Admins can select users, view their document permissions, and adjust document visibility.

- **`chat.py`**:  
  Facilitates a chat-based interface with language model integration, enabling conversational interactions.

- **`database.py`**:  
  Manages document and tag viewing. Users can see their documents, shared documents, and summaries if enabled. This file provides a tabbed interface for a more organized document display.

### Manager Files

Manager files handle data processing and integration across the app:

- **`document_manager.py`**:  
  Manages document processing, particularly PDF handling. It extracts and cleans text from PDFs, organizes pages with tags.

- **`llm_manager.py`**:  
  Interfaces with OpenAI language models for embedding generation tasks.

- **`pinecone_manager.py`**:  
  Configures and manages a Pinecone vector database, where document embeddings are stored and retrieved for similarity searches. This manager handles setting up and maintaining the Pinecone index.

- **`session_manager.py`**:  
  Manages user session data, including chat message transformation and caching.

- **`tag_manager.py`**:  
  Provides a tagging system for document categorization. Users can add and delete tags, which are validated against existing tags for consistency. Tag changes are transmitted to backend and synchronized with the session state.

### RAG File

- **`langchain_conversational_rag.py`**:  
  Implements retrieval-augmented generation (RAG), where relevant documents are retrieved based on user queries to enhance conversational responses. It uses LangChain to manage chat history, prompt templates, and retrieval chains. Integrates with Pinecone for document vector retrieval and OpenAI or Anthropic models for response generation.

---

### Getting Started

1. **Install Required Packages**:  
   Ensure that dependencies like Streamlit, Pinecone, OpenAI, LangChain are installed.
   
2. **Configure Secrets**:  
   Store sensitive keys (e.g., API keys for OpenAI and Pinecone, etc.) in the Streamlit `secrets` configuration file.

3. **Run the Application**:  
   Start the application by running `streamlit run index.py` from the terminal.

### Additional Information
- This app authenticates users using a JWT token provided as a query parameter. Once validated, the token is stored in cookies, allowing users to remain authenticated without re-entering the token each time.

---

### Example Streamlit Secrets

```
PINECONE_API_KEY = ""
OPENAI_API_KEY = ""
ANTHROPIC_API_KEY = ""
LANGCHAIN_API_KEY = ""
MODEL_OPTION = [ "gpt-4o-2024-08-06", "claude-3-5-sonnet-20241022" ]
INDEX_NAME = "demand-foresight"
ADMIN_NAME = "demandManager"
FRONTEND_URL = "https://livinglab-demand-foresight-dev.streamlit.app"
BACKEND_URL = "http://61.64.60.30/demand-foresight-backend"
COOKIES_PASSWORD = "221f8be27483c5fab6db40d618f7875f3dc22768960e3a43696552d28db03f94"

[prompts]
# Prompt name stored on langchain prompt hub
rag_contextualize_q_system_prompt = "rag_contextualize_q_system_prompt"
rag_system_prompt = "rag_system_prompt:f229d706"

[modules]
document_management = true
document_summarization = true
tag_editing = true
doc_chat = true

[rag]
# Number of documents to retrieve
top_k = 20
```
