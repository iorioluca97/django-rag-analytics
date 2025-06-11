from django.contrib import admin
from .models import Document, DocumentImage, Entity

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'uploaded_at', 'uploaded_by')  # colonne nella lista
    fields = ('title', 'file', 'uploaded_at', 'uploaded_by','size' )  # campi nel dettaglio
    readonly_fields = ('uploaded_at','raw_bytes')  # evita modifiche su questo campo

@admin.register(DocumentImage)
class DocumentImageAdmin(admin.ModelAdmin):
    list_display = ('id', 'image')

@admin.register(Entity)
class EntityAdmin(admin.ModelAdmin):
    list_display = ('id', 'document', 'text', 'label', 'start_pos', 'end_pos')
    list_filter = ('document', 'label')

