# llm/pdf_form_filler.py

from langchain_community.llms import Ollama

llm = Ollama(model="mistral")

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
