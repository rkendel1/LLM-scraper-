# backend/utils/delegation_model.py

from llm.pdf_form_filler import generate_with_mistral

def should_delegate_query(query: str) -> bool:
    prompt = f"""
    You are a decision-making assistant.

    The user asked: "{query}"

    Based on your knowledge, do you think this question requires input from a higher-level agency?
    For example:
    - It's about state/national laws
    - It's about specialized departments (e.g., energy, taxation)
    - It involves forms or tools only available externally

    Answer ONLY with YES or NO.
    """
    response = generate_with_mistral(prompt).strip().lower()
    return response == "yes"
