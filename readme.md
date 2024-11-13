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
  Facilitates a chat-based interface with language model integration, enabling conversational interactions. Conversations are stored in a Google Sheet, and each message thread can be titled for easy reference.

- **`database.py`**:  
  Manages document and tag viewing. Users can see their documents, shared documents, and summaries if enabled. This file provides a tabbed interface for a more organized document display.

### Manager Files

Manager files handle data processing and integration across the app:

- **`document_manager.py`**:  
  Manages document processing, particularly PDF handling. It extracts and cleans text from PDFs, organizes pages with tags, and integrates with `SheetManager`, `PineconeManager`, and `SessionManager` for document metadata and storage.

- **`llm_manager.py`**:  
  Interfaces with OpenAI and Gemini language models for tasks like text summarization and embedding generation. It includes prompt templates to ensure consistency in document summaries and interactions.

- **`pinecone_manager.py`**:  
  Configures and manages a Pinecone vector database, where document embeddings are stored and retrieved for similarity searches. This manager handles setting up and maintaining the Pinecone index.

- **`session_manager.py`**:  
  Manages user session data, including chat message transformation and caching. It formats message histories for consistent display and integrates with `SheetManager` and `PineconeManager`.

- **`sheet_manager.py`**:  
  Connects to Google Sheets for data storage and retrieval, facilitating real-time data updates. It manages API authentication and operations like reading and writing data to specific worksheets.

- **`tag_manager.py`**:  
  Provides a tagging system for document categorization. Users can add and delete tags, which are validated against existing tags for consistency. Tag changes are stored in Google Sheets and synchronized with the session state.

### RAG File

- **`langchain_conversational_rag.py`**:  
  Implements retrieval-augmented generation (RAG), where relevant documents are retrieved based on user queries to enhance conversational responses. It uses LangChain to manage chat history, prompt templates, and retrieval chains. Integrates with Pinecone for document vector retrieval and OpenAI or Anthropic models for response generation.

---

### Getting Started

1. **Install Required Packages**:  
   Ensure that dependencies like Streamlit, Pinecone, OpenAI, LangChain, and Google Sheets API are installed.
   
2. **Configure Secrets**:  
   Store sensitive keys (e.g., API keys for OpenAI, Pinecone, and Google Sheets) in the Streamlit `secrets` configuration file.

3. **Run the Application**:  
   Start the application by running `streamlit run index.py` from the terminal.

### Additional Information

- **Authentication**: The app uses a configuration file (`users.yaml`) for managing user credentials. This file should be configured securely and updated as needed.
- **Document Storage**: Document data is managed through Google Sheets, Pinecone, and session state.

---

### Example Streamlit Secrets

```
PINECONE_API_KEY = ""
OPENAI_API_KEY = ""
GEMINI_API_KEY = ""
ANTHROPIC_API_KEY = ""
LANGCHAIN_API_KEY = ""
MODEL_OPTION = [ "gpt-4o-2024-08-06", "claude-3-5-sonnet-20241022" ]
# Name of Pinecone index
INDEX_NAME = "demand-foresight"
# Website page name 
PAGE_TITLE = "International Cooperation"

[prompts]
# Prompt name stored on langchain prompt hub
rag_contextualize_q_system_prompt = "rag_contextualize_q_system_prompt"
rag_system_prompt = "rag_system_prompt:f229d706"

[modules]
authentication = false
document_management = true
document_sharing = true
document_summarization = false
tag_editing = false
doc_chat = false

[rag]
# Number of documents to retrieve
top_k = 20

[connection]
# Google sheet connection info
spreadsheet_id = ""

[connection.credentials]
type = ""
project_id = ""
private_key_id = ""
client_email = ""
client_id = ""
auth_uri = ""
token_uri = ""
auth_provider_x509_cert_url = ""
client_x509_cert_url = ""
```
