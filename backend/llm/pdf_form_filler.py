import os
from langchain_community.llms import Ollama

# Get host from env var or default to localhost
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# Initialize Ollama with custom host and model
llm = Ollama(
    model="mistral",
    base_url=OLLAMA_HOST
)

def generate_with_mistral(prompt):
    return llm.invoke(prompt).strip()

def generate_field_value(name, field_type):
    prompt = f"Generate realistic value for field '{name}' ({field_type})"
    return generate_with_mistral(prompt)

def fill_pdf_form(pdf_path, filled_path, field_data):
    from pypdf import PdfWriter, PdfReader

    reader = PdfReader(pdf_path)
    writer = PdfWriter()
    writer.append(reader)
    writer.update_page_form_field_values(writer.pages[0], field_data)

    with open(filled_path, "wb") as output_stream:
        writer.write(output_stream)