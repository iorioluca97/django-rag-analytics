from django.shortcuts import render
from .models import Document
from django.shortcuts import redirect
from .utils.utility_functions import generate_hash, extract_text_from_bytes

def home(request):
    # Fetch all documents to display on the home page
    documents = Document.objects.all()
    print(f"Fetched {documents.count()} documents from the database.")  # Debugging output
    return render(request, 'documents/home.html', {'documents': documents})

def upload_document(request):
    if request.method == 'POST' and request.FILES.get('file'):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        uploaded_file = request.FILES['file']
        uploaded_file.seek(0)
        document = Document.objects.create(
            file=uploaded_file, 
            title=uploaded_file.name,
            # id_hash=generate_hash(uploaded_file.name),
            uploaded_by=x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR'),
            raw_bytes=uploaded_file.read(),
            size=uploaded_file.size
        )
        return redirect('document_detail', doc_id=document.id) 
    else:
        return render(request, 'documents/upload_error.html')

def document_detail(request, doc_id):
    doc = Document.objects.get(id=doc_id)
    return render(request, 'documents/upload.html', {'document': doc})

def upload_error(request):
    return render(request, 'documents/upload_error.html')

def chunk_document(request, doc_id):
    """
    Placeholder for the chunk_document view.
    This function will handle the chunking of the document.
    """
    
    from .utils.text_extraction import TextExtractor
    te = TextExtractor(chunk_size=1000, chunk_overlap=200)
    doc = Document.objects.get(id=doc_id)
    print(f"Processing document with ID: {doc.id}, Title: {doc.title}, Url: {doc.file.url}")  # Debugging output
    
    if not doc.file:
        return render(request, 'documents/upload_error.html', {'error': 'Document file is missing.'})

    try:
        text = extract_text_from_bytes(doc.raw_bytes)

        print(f"Extracting text from document: {text[:50]}...")  # Debugging output to check the text content
        documents = te.extract_text(text)


        return render(request, 'documents/chunk_success.html', {
            'doc_id': doc.id,
            'documents': documents
        })
    except Exception as e:
        return render(request, 'documents/upload_error.html', {'error': str(e)})

def summarize_document(request, doc_id):
    """
    Placeholder for the summarize_document view.
    This function will handle the summarization of the document.
    """
    from .utils.text_summarization import summarize_text
    doc = Document.objects.get(id=doc_id)
    
    if not doc.file:
        return render(request, 'documents/upload_error.html', {'error': 'Document file is missing.'})

    try:
        text = extract_text_from_bytes(doc.raw_bytes)
        print(f"Extracting text from document: {text[:50]}...")
        summary = summarize_text(text)

        print(f"Summarizing document: {doc.title}, Summary: {summary[:50]}...")  # Debugging output to check the summary content
        
        return render(request, 'documents/summarize_success.html', {
            'doc_id': doc.id,
            'summary': summary
        })
    except Exception as e:
        return render(request, 'documents/upload_error.html', {'error': str(e)})

