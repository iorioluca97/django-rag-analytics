import time
from django.shortcuts import render
from .models import Document, DocumentImage
from django.shortcuts import redirect
from .utils.logger import logger
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
import json
from django.core.files.base import ContentFile
from .utils.text_extraction import DocumentExtractor
import os
from django.views.decorators.csrf import csrf_exempt
from dotenv import load_dotenv
from .utils.text_summarization import summarize_documents

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
    doc = Document.objects.get(id=doc_id)
    if not doc.file:
        return render(request, 'documents/upload_error.html', {'error': 'Document file is missing.'})
    
    logger.debug(f"Processing document with ID: {doc.id}, Title: {doc.title}, Url: {doc.file.url}")  # Debugging output
    document_extractor = DocumentExtractor(doc.raw_bytes)
    title_no_ext = doc.title.split('.pdf')[0] if doc.title else 'document'
    try:
        documents = document_extractor.extract_text()
        logger.debug(f"Extracted {len(documents)} chunks from the document.")


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
        response['Content-Disposition'] = f'attachment; filename="{title_no_ext}_chunks.json"'
        return response


    except Exception as e:
        return render(request, 'documents/upload_error.html', {'error': str(e)})

def summarize_document(request, doc_id):
    llm_settings = {
        "model" : request.POST.get('model_type'),
        "language": request.POST.get('language'),
        "temperature": float(request.POST.get('temperature', 0.5)),  # valore default 0.5
        "length": request.POST.get('length', 'short'),  # valore default 'short'
        "focus_areas": request.POST.get('focus_areas', None),
        # "style": request.POST.get('style'),
        # "include_quotes": True if 'include_quotes' in request.POST else False,
        # "bullet_points": True if 'bullet_points' in request.POST else False,
        # "include_stats": True if 'include_stats' in request.POST else False
    }
    
    doc = Document.objects.get(id=doc_id)
    title_no_ext = doc.title.split('.pdf')[0] if doc.title else 'document'
    if not doc.file:
        return render(request, 'documents/upload_error.html', {'error': 'Document file is missing.'})

    try:
        document_extractor = DocumentExtractor(doc.raw_bytes)
        documents = document_extractor.extract_text()
        summary = summarize_documents(documents, llm_settings)

        logger.debug(f"Generated summary: {summary[:1000]}...")  # Log the first 1000 characters of the summary

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

def analyze_document(request, doc_id):
    doc = Document.objects.get(id=doc_id)
    if not doc.file:
        return render(request, 'documents/upload_error.html', {'error': 'Document file is missing.'})

    logger.debug(f"Processing document with ID: {doc.id}, Title: {doc.title}, Url: {doc.file.url}")

    doc_extractor = DocumentExtractor(doc.raw_bytes)

    try:
        start_time = time.time()
        toc = doc_extractor.extract_toc()
        chunks = doc_extractor.extract_text()
        full_text = " ".join(chunk.page_content for chunk in chunks)
        

        # Altri metadati
        language = doc_extractor.detect_language(full_text)
        reading_time = doc_extractor.estimate_reading_time(full_text)
        page_numbers = doc_extractor.page_count
        words_count = doc_extractor.get_words_count(full_text)
        images_extracted = doc_extractor.extract_images()

        for i, image in enumerate(images_extracted, start=1):
            image_name = f"image_{i}_page_{image['page_number']}.png"
            DocumentImage.objects.create(
                image=ContentFile(image["base64_data"], name=image_name),
                document=doc,
                page_number=image['page_number']
            )

        end_time = time.time()
        elapsed_time = round(end_time - start_time, 2)

         #TODO: Implement the NER extraction logic
        # text_extracted = doc_extractor.extract_text(text)
        # entities = doc_extractor.extract_entities(text_extracted)

        # for ent in entities:
        #     Entity.objects.create(
        #         document=doc,
        #         text=ent["text"],
        #         label=ent["label"],
        #         start_pos=ent["start"],
        #         end_pos=ent["end"]
        #     )

        #TODO: Implement the MongoDB indexing logic
        # from .utils.text_embedding import MongoDb
        # mongodb = MongoDb(collection_name=doc.title.replace(' ', '_').lower())
        # mongodb.index_chunks(documents, doc)

        # Log the time taken for text extraction
        end_time = time.time()
        elapsed_time = end_time - start_time

        return render(request, 'documents/analytics.html', {
            'document': doc, 
            'toc': toc, 
            'images': images_extracted,
            'page_numbers': page_numbers,
            'images_count': len(images_extracted),
            'words_count': words_count,
            'elapsed_time': round(elapsed_time, 2),
            'reading_time': reading_time,
            'language': language.upper(),

        })
    except Exception as e:
        return render(request, 'documents/upload_error.html', {'error': str(e)})
        
def chat(request, doc_id):
    """
    Placeholder for the chat view.
    This function will handle the chat functionality.
    """
    return render(request, 'documents/chat.html', {
        'doc_id': doc_id,
        'document': Document.objects.get(id=doc_id)
    })


@csrf_exempt
def save_env_keys(request):
    if request.method == 'POST':
        openai_key = request.POST.get('openai_key')
        mongo_uri = request.POST.get('mongo_uri')

        # Clear the environment variables in memory
        os.environ.pop('OPENAI_API_KEY', None)
        os.environ.pop('MONGO_URI', None)

        load_dotenv()

        os.environ['OPENAI_API_KEY'] = openai_key
        os.environ['MONGO_URI'] = mongo_uri

        # Save the keys to the .env file
        with open('./.env', 'a') as env_file:
            env_file.write(f'\nOPENAI_API_KEY={openai_key}\n')
            env_file.write(f'MONGO_URI={mongo_uri}\n')

        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)
