# documents/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # Puoi mettere una view fittizia per iniziare
    path('', views.home, name='home'),
    # URL per caricare documenti
    path('upload', views.upload_document, name='upload_document'),
]