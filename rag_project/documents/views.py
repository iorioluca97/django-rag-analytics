from django.shortcuts import render
from .models import Document
from django.shortcuts import redirect
from .utils.utility_functions import extract_text_from_bytes
from .utils.logger import logger
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
import json

def home(request):
    # Fetch all documents to display on the home page
    documents = Document.objects.all().order_by('-uploaded_at')
    logger.debug(f"Fetched {documents.count()} documents from the database.")
    return render(request, 'documents/home.html', {'documents': documents})

def upload_document(request):
    if request.method == 'POST' and request.FILES.get('file'):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        uploaded_file = request.FILES['file']
        uploaded_file.seek(0)
        document = Document.objects.create(
            file=uploaded_file, 
            title=uploaded_file.name,
            uploaded_by=x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR'),
            raw_bytes=uploaded_file.read(),
            size=uploaded_file.size
        )
        return redirect('document_detail', doc_id=document.id) 
    else:
        return render(request, 'documents/upload_error.html')

def document_detail(request, doc_id):
    doc = Document.objects.get(id=doc_id)
    return render(request, 'documents/document.html', {'document': doc})

def upload_error(request):
    return render(request, 'documents/upload_error.html')

def chunk_document(request, doc_id):    
    from .utils.text_extraction import TextExtractor

    te = TextExtractor(chunk_size=1000, chunk_overlap=200)
    doc = Document.objects.get(id=doc_id)
    logger.debug(f"Processing document with ID: {doc.id}, Title: {doc.title}, Url: {doc.file.url}")  # Debugging output
    if not doc.file:
        return render(request, 'documents/upload_error.html', {'error': 'Document file is missing.'})
    title_no_ext = doc.title.split('.pdf')[0] if doc.title else 'document'
    try:
        text = extract_text_from_bytes(doc.raw_bytes)
        documents = te.extract_text(text)
        logger.debug(f"Extracted {len(documents)} chunks from the document.")
        logger.debug(documents)
        complete_result = {
            'metadata': {
                'doc_id': doc.id,
                'doc_title': doc.title,
                'doc_url': doc.file.url,
                'doc_size': doc.size,
                'chunks_count': len(documents)
            },
            'chunks': []
        }
        for doc in documents:
            complete_result['chunks'].append({
                'chunk_text': doc.page_content,
                'chunk_metadata': doc.metadata
            })

        # Convert the result to a JSON string
        json_string = json.dumps(complete_result, indent=2)
        
        # Create an HTTP response with the JSON data
        response = HttpResponse(json_string, content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename="{title_no_ext}_summary.json"'
        return response


    except Exception as e:
        return render(request, 'documents/upload_error.html', {'error': str(e)})

def summarize_document(request, doc_id):
    from .utils.text_summarization import summarize_text
    doc = Document.objects.get(id=doc_id)
    title_no_ext = doc.title.split('.pdf')[0] if doc.title else 'document'
    if not doc.file:
        return render(request, 'documents/upload_error.html', {'error': 'Document file is missing.'})

    try:
        text = extract_text_from_bytes(doc.raw_bytes)
        summary = summarize_text(text)

        response = HttpResponse(summary, content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename="{title_no_ext}_summary.txt"'
        return response
    
    except Exception as e:
        return render(request, 'documents/upload_error.html', {'error': str(e)})

def serve_pdf(request, document_id):

    document = get_object_or_404(Document, id=document_id)
    
    response = HttpResponse(document.raw_bytes, content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="document.pdf"'
    response['Content-Length'] = len(document.raw_bytes)
    
    # Header per permettere l'embedding
    response['X-Frame-Options'] = 'SAMEORIGIN'
    response['Content-Security-Policy'] = "frame-ancestors 'self'"
    
    # Cache headers
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    
    return response

def index_document(request, doc_id):
    """
    Placeholder for the index_document view.
    This function will handle the indexing of the document.
    """
    #TODO: Implement the indexing logic
    # from .utils.text_embedding import MongoDb
    # mongodb = MongoDb(collection_name=doc.title.replace(' ', '_').lower())
    # mongodb.index_chunks(documents, doc)

    # return render(request, 'documents/chunk_success.html', {
    #     'doc_id': doc.id,
    #     'documents': documents
    # })
    return redirect('document_detail', doc_id=doc_id)