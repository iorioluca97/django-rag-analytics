# Create a simple hash function to generate a hash from the document title
import hashlib
import io
import PyPDF2

def generate_hash(title):
    """
    Generate a SHA-256 hash from the document title.
    
    Args:
        title (str): The title of the document.
        
    Returns:
        str: The SHA-256 hash of the title.
    """
    if not title:
        raise ValueError("Title cannot be empty")
    return hashlib.sha256(title.encode('utf-8')).hexdigest()


def extract_text_from_bytes(pdf_bytes):
    pdf_file = io.BytesIO(pdf_bytes)
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    
    text = ""
    for page_num, page in enumerate(pdf_reader.pages):
        page_text = page.extract_text()
        text += f"\n--- Page {page_num + 1} ---\n"
        text += page_text
    
    return text