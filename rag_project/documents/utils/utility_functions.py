import io
import PyPDF2

# Dictionary to map opeanai model names to their correspondiing max tokens
def get_max_tokens(model_name):
    model_max_tokens = {
        "gpt-3.5-turbo": 4096,
        "gpt-4": 8192,
        "gpt-4-32k": 32768,
        "gpt-3.5-turbo-16k": 16384,
    }
    return model_max_tokens.get(model_name, 4096)  # Default to 4096 if not found

def extract_text_from_bytes(pdf_bytes):
    pdf_file = io.BytesIO(pdf_bytes)
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    
    text = ""
    for page_num, page in enumerate(pdf_reader.pages):
        page_text = page.extract_text()
        text += f"\n--- Page {page_num + 1} ---\n"
        text += page_text
    
    return text