from django.contrib import admin
from .models import Document, DocumentImage, Entity, DocumentAnalytics

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'original_title', 'uploaded_at', 'uploaded_by')  # colonne nella lista
    fields = ('title', 'original_title', 'file', 'uploaded_at', 'uploaded_by', 'size')  # campi nel dettaglio
    readonly_fields = ('uploaded_at', 'raw_bytes')  # evita modifiche su questo campo

@admin.register(DocumentImage)
class DocumentImageAdmin(admin.ModelAdmin):
    list_display = ('id', 'image', 'document', 'page_number', 'extracted_at')

@admin.register(Entity)
class EntityAdmin(admin.ModelAdmin):
    list_display = ('id', 'document', 'text', 'label', 'start_pos', 'end_pos')
    list_filter = ('document', 'label')


@admin.register(DocumentAnalytics)
class DocumentAnalyticsAdmin(admin.ModelAdmin):
    list_display = ('id', 'document', 'analyzed_at', 'page_count', 'words_count', 'images_extracted_count')
    list_filter = ('document', 'analyzed_at')
    readonly_fields = ('toc', 'full_text', 'language', 'reading_time')