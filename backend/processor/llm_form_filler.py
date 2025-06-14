from langchain_community.llms import Ollama
import json

llm = Ollama(model="mistral")

def generate_field_value(field_name, field_type):
    prompt = f"""
    Generate a realistic value for the following PDF form field:
    
    Field Name: {field_name}
    Field Type: {field_type}  # e.g., text, dropdown, checkbox
    
    Return only the value, no explanation.
    """
    return llm.invoke(prompt).strip()
