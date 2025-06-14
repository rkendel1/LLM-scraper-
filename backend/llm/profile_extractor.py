# llm/profile_extractor.py

from langchain_core.messages import HumanMessage
from llm.prompt_templates import ADDRESS_EXTRACTION_PROMPT
from llm.pdf_form_filler import generate_with_mistral
from utils.user_utils import update_user_profile

def extract_and_save_profile_info(user_id, input_text):
    prompt = ADDRESS_EXTRACTION_PROMPT.format(input=input_text)
    response = generate_with_mistral(prompt)

    try:
        profile_data = json.loads(response)
        for key, value in profile_data.items():
            update_user_profile(user_id, {"key": key, "value": value})
        return profile_data
    except:
        return None
