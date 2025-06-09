from django.contrib import admin
from .models import Document

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'uploaded_at', 'uploaded_by')  # colonne nella lista
    fields = ('title', 'file', 'uploaded_at', 'uploaded_by','size' )  # campi nel dettaglio
    readonly_fields = ('uploaded_at','raw_bytes')  # evita modifiche su questo campo

