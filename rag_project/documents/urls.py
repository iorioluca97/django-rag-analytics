# documents/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # Puoi mettere una view fittizia per iniziare
    path('', views.home, name='home'),
    # URL per caricare documenti
    path('document', views.upload_document, name='upload_document'),
    path('<int:doc_id>/', views.document_detail, name='document_detail'),
    path('error', views.upload_error, name='upload_error'),
    # URL per gestire il chunking dei documenti
    path('chunking/<int:doc_id>/', views.chunk_document, name='chunk_document'),
    # URL per gestire la sintesi dei documenti
    path('summarize/<int:doc_id>/', views.summarize_document, name='summarize_document'),
]