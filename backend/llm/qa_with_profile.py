# llm/qa_with_profile.py

from langchain.chains import LLMChain
from llm.prompt_templates import QA_WITH_PROFILE_PROMPT
from llm.pdf_form_filler import generate_with_mistral

def ask_with_profile(question, profile):
    prompt = QA_WITH_PROFILE_PROMPT.format(profile=profile, question=question)
    return generate_with_mistral(prompt)
