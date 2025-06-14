# llm/prompt_templates.py

from langchain.prompts import ChatPromptTemplate

RAG_PROMPT_TEMPLATE = """
You are a helpful assistant.
Use the following context to answer the question.

Context:
{context}

Question:
{question}

Answer:
"""

ADDRESS_EXTRACTION_PROMPT = """
You are a profile assistant.
Detect and extract any personal information like name, address, phone number, etc.

Input: "{input}"

Output only the extracted values in JSON format.
"""

QA_WITH_PROFILE_PROMPT = """
You are answering based on knowledge and user profile.

Profile:
{profile}

Question:
{question}

Answer:
"""
