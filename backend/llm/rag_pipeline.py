import os
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_postgres import PGVector
from langchain_community.llms import Ollama
from langchain.prompts import ChatPromptTemplate
from config.settings import settings
from sentence_transformers import SentenceTransformerEmbeddings

CONNECTION_STRING = settings.DATABASE_URL
COLLECTION_NAME = "document_embeddings"

# Get host from env var or default to localhost
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# Initialize LLM with dynamic host
llm = Ollama(
    model="mistral",
    base_url=OLLAMA_HOST
)

embeddings = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")

db = PGVector(
    connection_string=CONNECTION_STRING,
    collection_name=COLLECTION_NAME,
    embedding_function=embeddings
)

retriever = db.as_retriever(search_type="similarity", search_kwargs={"k": 5})

RAG_PROMPT_TEMPLATE = """
<context>
{context}
</context>

Question: {input}

Answer:
"""

prompt = ChatPromptTemplate.from_template(RAG_PROMPT_TEMPLATE)

question_answer_chain = create_stuff_documents_chain(llm, prompt)
rag_chain = create_retrieval_chain(retriever, question_answer_chain)

def build_rag_pipeline():
    return rag_chain