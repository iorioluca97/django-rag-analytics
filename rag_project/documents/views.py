import time
from django.shortcuts import render
from .models import Document, DocumentImage, DocumentAnalytics
from django.shortcuts import redirect
from .utils.logger import logger
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
import json
from django.core.files.base import ContentFile
from .utils.text_extraction import DocumentExtractor
from .utils.vector_db import MongoDb
import os
from django.views.decorators.csrf import csrf_exempt
from dotenv import load_dotenv, set_key, dotenv_values
from .utils.text_summarization import summarize_documents
from .utils.RAG import RAG
from .utils.document_conversion import FactoryConversion
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any

CONVERT_OPTIONS = [
    {"value": "pdf", "label": "PDF - Documento Portabile"},
    {"value": "docx", "label": "DOCX - Word"},
    {"value": "txt", "label": "TXT - Testo semplice"},
    {"value": "html", "label": "HTML - Pagina Web"},
]

# Multi-threading helper functions for document analysis
def extract_content_thread(doc_extractor: DocumentExtractor, raw_bytes: bytes) -> Dict[str, Any]:
    """Thread 1: Extract TOC, text chunks, and tables"""
    logger.debug("Thread 1: Starting content extraction...")
    
    toc = doc_extractor.extract_toc()
    chunks = doc_extractor.extract_text()
    full_text = " ".join(chunk.page_content for chunk in chunks)
    dfs_extracted, jsons_extracted = doc_extractor.extract_tables(
        raw_bytes, min_words_in_row=1)
    
    logger.debug(f"Thread 1: Extracted {len(chunks)} chunks, {len(jsons_extracted)} tables")
    
    return {
        'toc': toc,
        'chunks': chunks,
        'full_text': full_text,
        'tables_dfs': dfs_extracted,
        'tables_json': jsons_extracted
    }

def extract_metadata_thread(doc_extractor: DocumentExtractor, full_text: str) -> Dict[str, Any]:
    """Thread 2: Extract language, reading time, and word count"""
    logger.debug("Thread 2: Starting metadata extraction...")
    
    language = doc_extractor.detect_language(full_text)
    reading_time = doc_extractor.estimate_reading_time(full_text)
    words_count = doc_extractor.get_words_count(full_text)
    page_count = doc_extractor.page_count
    
    logger.debug(f"Thread 2: Language: {language}, Words: {words_count}, Reading time: {reading_time}min")
    
    return {
        'language': language,
        'reading_time': reading_time,
        'words_count': words_count,
        'page_count': page_count
    }

def extract_images_thread(doc_extractor: DocumentExtractor, document: Document) -> Dict[str, Any]:
    """Thread 3: Extract and save images"""
    logger.debug("Thread 3: Starting image extraction...")
    
    images_extracted = doc_extractor.extract_images()
    
    # Save images to database
    for i, image in enumerate(images_extracted, start=1):
        DocumentImage.objects.create(
            image=image["raw_bytes"],
            document=document,
            page_number=image['page_number']
        )
    
    logger.debug(f"Thread 3: Extracted and saved {len(images_extracted)} images")
    
    return {
        'images': images_extracted,
        'images_count': len(images_extracted)
    }

def index_mongodb_thread(chunks, document: Document) -> Dict[str, Any]:
    """Thread 4: Index chunks in MongoDB"""
    logger.debug("Thread 4: Starting MongoDB indexing...")
    
    if not os.getenv("MONGO_URI"):
        logger.warning("Thread 4: MONGO_URI is not set, skipping indexing.")
        return {'mongodb_indexed': False, 'error': 'MONGO_URI not set'}
    
    try:
        db = MongoDb(collection_name=document.title)
        db.index_chunks(chunks, document)
        logger.debug(f"Thread 4: Successfully indexed {len(chunks)} chunks")
        return {'mongodb_indexed': True, 'chunks_count': len(chunks)}
    except Exception as e:
        logger.error(f"Thread 4: Error indexing document chunks: {str(e)}")
        return {'mongodb_indexed': False, 'error': str(e)}

def home(request):
    # Simple home page with upload form and OpenAI key configuration
    logger.debug("Rendering home page.")
    return render(request, 'documents/home.html')

def upload_document(request):
    if request.method == 'POST' and request.FILES.get('file'):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        uploaded_file = request.FILES['file']
        uploaded_file.seek(0)

        cleaned_title = uploaded_file.name.split('.')[0].lower() # Get the file name without extension
        document = Document.objects.create(
            file=uploaded_file, 
            title=cleaned_title,
            original_title=uploaded_file.name,
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

    doc = Document.objects.get(id=doc_id) or render(request, 'documents/upload_error.html', {'error': 'Document not found.'})
    

    # Get the document analytics
    analytics = DocumentAnalytics.objects.filter(document=doc).first()
    if analytics:
        # If analytics already exist, render the analytics page
        logger.debug(f"Document analytics found for document ID: {doc.id}, Title: {doc.title}")

        doc_extractor = DocumentExtractor(doc.raw_bytes)
        dfs_extracted, jsons_extracted = doc_extractor.extract_tables(
            doc.raw_bytes, min_words_in_row=1)

        if jsons_extracted:
            logger.debug(f"Extracted {len(jsons_extracted)} tables from the document.")
        images_extracted = doc_extractor.extract_images()

        logger.debug(jsons_extracted)

        return render(request, 'documents/analytics.html', {
            'document': doc,
            'toc': analytics.toc,
            'full_text': analytics.full_text,
            'language': analytics.language,
            'reading_time': analytics.reading_time,
            'page_numbers': analytics.page_count,
            'words_count': analytics.words_count,
            'images_count': len(images_extracted),
            'elapsed_time': round((analytics.analyzed_at - doc.uploaded_at).total_seconds(), 2),
            'images': images_extracted,
            'tables_count': len(jsons_extracted),
            'tables': jsons_extracted,
        })

    # Document does not have analytics, proceed with extraction
    logger.debug(f"Processing document with ID: {doc.id}, Title: {doc.title}, Url: {doc.file.url}")
    try:
        doc_extractor = DocumentExtractor(doc.raw_bytes)
        start_time = time.time()
        
        # Initialize results containers
        content_result = {}
        metadata_result = {}
        images_result = {}
        mongodb_result = {}
        
        # Execute extraction tasks in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as executor:
            logger.debug("Starting multi-threaded document analysis...")
            
            # Submit Thread 1: Content extraction (TOC, text, tables)
            content_future = executor.submit(extract_content_thread, doc_extractor, doc.raw_bytes)
            
            # Wait for content to extract full_text before starting metadata thread
            content_result = content_future.result()
            full_text = content_result['full_text']
            
            # Now submit remaining threads with dependencies resolved
            futures = {
                'metadata': executor.submit(extract_metadata_thread, doc_extractor, full_text),
                'images': executor.submit(extract_images_thread, doc_extractor, doc),
                'mongodb': executor.submit(index_mongodb_thread, content_result['chunks'], doc)
            }
            
            # Collect results as they complete
            for future_name, future in futures.items():
                try:
                    result = future.result(timeout=300)  # 5 minute timeout
                    if future_name == 'metadata':
                        metadata_result = result
                    elif future_name == 'images':
                        images_result = result
                    elif future_name == 'mongodb':
                        mongodb_result = result
                    logger.debug(f"Thread completed: {future_name}")
                except Exception as e:
                    logger.error(f"Thread {future_name} failed: {str(e)}")
                    # Set default values for failed threads
                    if future_name == 'metadata':
                        metadata_result = {
                            'language': 'unknown',
                            'reading_time': 0,
                            'words_count': 0,
                            'page_count': doc_extractor.page_count
                        }
                    elif future_name == 'images':
                        images_result = {'images': [], 'images_count': 0}
                    elif future_name == 'mongodb':
                        mongodb_result = {'mongodb_indexed': False, 'error': str(e)}

        # Calculate elapsed time
        end_time = time.time()
        elapsed_time = round(end_time - start_time, 2)
        
        logger.debug(f"Multi-threaded analysis completed in {elapsed_time}s")
        
        # Extract values from results
        toc = content_result.get('toc', [])
        chunks = content_result.get('chunks', [])
        full_text = content_result.get('full_text', '')
        jsons_extracted = content_result.get('tables_json', [])
        
        language = metadata_result.get('language', 'unknown')
        reading_time = metadata_result.get('reading_time', 0)
        words_count = metadata_result.get('words_count', 0)
        page_numbers = metadata_result.get('page_count', 0)
        
        images_extracted = images_result.get('images', [])
        images_count = images_result.get('images_count', 0)

        # Save analytics to the database
        analytics = DocumentAnalytics(
            document=doc,
            toc=toc,
            full_text=full_text,
            language=language,
            reading_time=reading_time,
            page_count=page_numbers,
            words_count=words_count,
            images_extracted_count=images_count
        )
        analytics.save()

        # Log MongoDB indexing results
        if mongodb_result.get('mongodb_indexed'):
            logger.info(f"Successfully indexed {mongodb_result.get('chunks_count', 0)} chunks to MongoDB")
        else:
            logger.warning(f"MongoDB indexing failed: {mongodb_result.get('error', 'Unknown error')}")

        return render(request, 'documents/analytics.html', {
            'document': doc, 
            'toc': toc, 
            'images': images_extracted,
            'page_numbers': page_numbers,
            'images_count': len(images_extracted),
            'words_count': words_count,
            'elapsed_time': elapsed_time,
            'reading_time': reading_time,
            'language': language.upper(),
            'tables_count': len(jsons_extracted),
            'tables': jsons_extracted,
            'mongodb_indexed': mongodb_result.get('mongodb_indexed', False),
        })
    except Exception as e:
        return render(request, 'documents/upload_error.html', {'error': str(e)})
        
def chat(request, doc_id):
    """
    Placeholder for the chat view.
    This function will handle the chat functionality.
    """
    doc = Document.objects.get(id=doc_id) or render(request, 'documents/upload_error.html', {'error': 'Document not found.'})
    analytics = DocumentAnalytics.objects.filter(document=doc).first()
    if not analytics:
        return render(request, 'documents/upload_error.html', {'error': 'Document analytics not found.'})
    
    # If analytics exist, render the chat page
    return render(request, 'documents/chat.html', {
        'doc_id': doc_id,
        'document': Document.objects.get(id=doc_id),
        'analytics': analytics
    })


@csrf_exempt
def ask_question(request, doc_id):
    if request.method == "POST":
        data = json.loads(request.body)
        if not data.get("text"):
            return JsonResponse({"status": "error", "message": "Text is required."}, status=400)
        
        rag = RAG(
            mongo_uri=os.getenv("MONGO_URI"),
            database_name="django_rag_analytics",
            top_k_documents=5,  # You can adjust this value based on your needs
            collection_name=Document.objects.get(id=doc_id).title
        )
        # Process the user query
        response = rag.answer_question(user_query=data.get("text"), )
        
        # Return the response as JSON
        return JsonResponse({
            "status": "success",
            "rag_response": response,
            "status_code": 200,
        })

def delete_analytics(request):
    """
    Deletes the analytics for a specific document.
    """
    try:
        if request.method == 'DELETE':
            data = json.loads(request.body)
            doc_id = data.get('doc_id')
            if not doc_id:
                return JsonResponse({'status': 'error', 'message': 'Document ID is required.'}, status=400)

            logger.debug(f"Attempting to delete analytics for document ID: {doc_id}")
        doc = Document.objects.get(id=doc_id)
        analytics = DocumentAnalytics.objects.filter(document=doc).first()
        images = DocumentImage.objects.filter(document=doc)
        if analytics:
            analytics.delete()
            logger.info(f"Deleted analytics for document ID: {doc_id}")
        if images:
            images.delete()
            logger.info(f"Deleted images for document ID: {doc_id}")
            return JsonResponse({
                'status_code': 200,
                'status': 'success', 
                'message': 'Analytics deleted successfully.', })
        else:
            logger.warning(f"No analytics found for document ID: {doc_id}")
            return render(request, 'documents/upload_error.html', {'error': 'No analytics found for this document.'})
    except Document.DoesNotExist:
        logger.error(f"Document with ID {doc_id} does not exist.")
        return render(request, 'documents/upload_error.html', {'error': 'Document analytics not found.'})


def convert_landing_page(request, doc_id):    
    doc = Document.objects.get(id=doc_id)
    if not doc.file:
        return render(request, 'documents/upload_error.html', {'error': 'Document file is missing.'})
    
    logger.debug(f"Processing document with ID: {doc.id}, Title: {doc.title}, Url: {doc.file.url}")  # Debugging output
    document_extractor = DocumentExtractor(doc.raw_bytes)

    file_name = doc.file.name  
    _, file_extension = os.path.splitext(file_name)  
    file_extension = file_extension.lower().lstrip('.')
    

    return render(request, 'documents/convert.html', {
        "document": doc,
        "bytes" : doc.raw_bytes,
        "file_extension": file_extension,
        "convert_options": CONVERT_OPTIONS,})

def convert_document(request, doc_id):
    logger.info('DATA: ')
    logger.info(request)
    data = json.loads(request.body)
    logger.info('DATA: ')
    logger.info(data)
    converted_document = FactoryConversion.convert(
        input_file_extension=data.get('input_file_extension'),
        output_file_extension=data.get('output_file_extension'),
        file_bytes=data.get('file_bytes')
    )

    output_extension = data.get('output_file_extension', 'bin').lower()
    filename = f"converted_document.{output_extension}"

    response = HttpResponse(
        converted_document,
        content_type='application/octet-stream'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response

@csrf_exempt
def save_env_keys(request):
    if request.method == 'POST':
        openai_key = request.POST.get('openai_key')
        
        if not openai_key:
            return JsonResponse({'status': 'error', 'message': 'OpenAI API Key is required'}, status=400)

        env_path = './.env'

        # Set and persist only the OpenAI API key
        set_key(env_path, 'OPENAI_API_KEY', openai_key)

        # Ricarica il file in os.environ (non solo scrittura)
        load_dotenv(dotenv_path=env_path, override=True)

        logger.info("OpenAI API Key updated successfully")
        return JsonResponse({'status': 'success', 'message': 'OpenAI API Key saved successfully'})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=400)

