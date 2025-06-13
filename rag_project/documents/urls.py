# documents/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # Puoi mettere una view fittizia per iniziare
    path('', views.home, name='home'),
    # URL per caricare documenti
    path('document', views.upload_document, name='upload_document'),
    # URL per visualizzare i dettagli di un documento
    path('<int:doc_id>/', views.document_detail, name='document_detail'),
    # URL per gestire gli errori di caricamento
    path('error', views.upload_error, name='upload_error'),
    # URL per gestire il chunking dei documenti
    path('chunking/<int:doc_id>/', views.chunk_document, name='chunk_document'),
    # URL per gestire la sintesi dei documenti
    path('summarize/<int:doc_id>/', views.summarize_document, name='summarize_document'),
    # URL per servire il PDF
    path('<int:document_id>/pdf/', views.serve_pdf, name='serve_pdf'),
    # URL per la chat
    path('chat/<int:doc_id>/', views.chat, name='chat'),
    # URL per l analisi dei documenti
    path('analytics/<int:doc_id>/', views.analyze_document, name='analyze_document'),
    # URL per salvare le chiavi dell'ambiente
    path('save-env-keys/', views.save_env_keys, name='save_env_keys'),
    # URL per inviare un messaggio
    path("chat/<int:doc_id>/ask-question/", views.ask_question, name="ask-question")



]