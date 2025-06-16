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
        toc = doc_extractor.extract_toc()
        chunks = doc_extractor.extract_text()
        full_text = " ".join(chunk.page_content for chunk in chunks)
        
        # Altri metadati
        language = doc_extractor.detect_language(full_text)
        reading_time = doc_extractor.estimate_reading_time(full_text)
        page_numbers = doc_extractor.page_count
        words_count = doc_extractor.get_words_count(full_text)
        images_extracted = doc_extractor.extract_images()
        dfs_extracted, jsons_extracted = doc_extractor.extract_tables(
            doc.raw_bytes, min_words_in_row=1)

        if jsons_extracted:
            logger.debug(f"Extracted {len(jsons_extracted)} tables from the document.")
        logger.debug(f"Extracted {len(dfs_extracted)} tables from the document.")

        for i, image in enumerate(images_extracted, start=1):
            # Save the image as a binary field
            DocumentImage.objects.create(
                image=image["raw_bytes"],
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

        # Log the time taken for text extraction
        end_time = time.time()
        elapsed_time = end_time - start_time

        # Save analytics to the database
        analytics = DocumentAnalytics(
            document=doc,
            toc=toc,
            full_text=full_text,
            language=language,
            reading_time=reading_time,
            page_count=page_numbers,
            words_count=words_count,
            images_extracted_count=len(images_extracted)
        )
        analytics.save()

        try:
            db = MongoDb(collection_name=doc.title)
            db.index_chunks(chunks, doc)
        except ValueError as e:
            logger.error(f"Error indexing document chunks for document ID: {doc.id}, Title: {doc.title}, Error: {str(e)}")

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
            'tables_count': len(jsons_extracted),
            'tables': jsons_extracted,

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

@csrf_exempt
def save_env_keys(request):
    if request.method == 'POST':
        openai_key = request.POST.get('openai_key')
        mongo_uri = request.POST.get('mongo_uri')

        env_path = './.env'

        # Set and persist the values
        set_key(env_path, 'OPENAI_API_KEY', openai_key)
        set_key(env_path, 'MONGO_URI', mongo_uri)

        # Ricarica il file in os.environ (non solo scrittura)
        load_dotenv(dotenv_path=env_path, override=True)

        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)

