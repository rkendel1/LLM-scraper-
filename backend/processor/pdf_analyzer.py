from pypdf import PdfReader

def analyze_pdf_form(pdf_path):
    try:
        reader = PdfReader(pdf_path)
        if '/AcroForm' in reader.trailer['/Root'].keys():
            fields = reader.trailer['/Root']['/AcroForm']['/Fields']
            field_info = []
            for field in fields:
                obj = field.get_object()
                name = obj.get('/T', '')
                value = obj.get('/V', '')
                field_type = obj.get('/FT', '')  # /Tx, /Btn, /Ch
                field_info.append({
                    'name': name,
                    'value': value,
                    'type': field_type
                })
            return {'is_form': True, 'fields': field_info}
        else:
            return {'is_form': False, 'fields': []}
    except Exception as e:
        print(f"Error analyzing PDF: {e}")
        return {'is_form': False, 'fields': []}
