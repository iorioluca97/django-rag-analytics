from django import forms
from .models import Document

class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['file']  # Assumendo che tu abbia un campo 'file' nel modello
