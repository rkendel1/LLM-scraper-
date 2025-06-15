import requests
import tempfile
from pypdf import PdfReader

def download_pdf(url):
    try:
        # Download PDF to a temporary file
        response = requests.get(url)
        response.raise_for_status()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(response.content)
            tmp_path = tmp_file.name

        # Analyze using PdfReader
        reader = PdfReader(tmp_path)
        if '/AcroForm' in reader.trailer['/Root']:
            fields = reader.trailer['/Root']['/AcroForm']['/Fields']
            field_info = []
            for field in fields:
                obj = field.get_object()
                name = obj.get('/T', '')
                value = obj.get('/V', '')
                field_type = obj.get('/FT', '')
                field_info.append({
                    'name': name,
                    'value': value,
                    'type': field_type
                })
            return {'is_form': True, 'fields': field_info}
        else:
            return {'is_form': False, 'fields': []}

    except Exception as e:
        print(f"Error downloading or analyzing PDF: {e}")
        return {'is_form': False, 'fields': []}