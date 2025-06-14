# llm/rag_pipeline.py

from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_postgres import PGVector
from langchain_openai import OpenAI  # Or use Ollama
from langchain.prompts import ChatPromptTemplate
from config.settings import settings

CONNECTION_STRING = settings.DATABASE_URL
COLLECTION_NAME = "document_embeddings"

def build_rag_pipeline():
    embeddings = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")
    db = PGVector(
        connection_string=CONNECTION_STRING,
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings
    )
    retriever = db.as_retriever(search_type="similarity", search_kwargs={"k": 5})

    model = Ollama(model="mistral")
    
    prompt = ChatPromptTemplate.from_template(RAG_PROMPT_TEMPLATE)

    question_answer_chain = create_stuff_documents_chain(model, prompt)
    rag_chain = create_retrieval_chain(retriever, question_answer_chain)

    return rag_chain
