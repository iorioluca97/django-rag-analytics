from django.shortcuts import render
from .forms import DocumentForm

def home(request):
    return render(request, 'documents/home.html')

def upload_document(request):
    form = DocumentForm()
    return render(request, 'documents/upload.html', {'form': form})

