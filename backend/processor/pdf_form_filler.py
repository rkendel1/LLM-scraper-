from pypdf import PdfWriter, PdfReader

def fill_pdf_form(input_path, output_path, field_data):
    reader = PdfReader(input_path)
    writer = PdfWriter()

    writer.append(reader)
    writer.update_page_form_field_values(writer.pages[0], field_data)

    with open(output_path, "wb") as output_stream:
        writer.write(output_stream)
