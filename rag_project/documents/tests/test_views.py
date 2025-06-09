from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from documents.models import Document
import io

class DocumentViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.document = Document.objects.create(
            title="Test File",
            file=SimpleUploadedFile("test.txt", b"Hello World"),
            raw_bytes=b"Hello World",
            uploaded_by="127.0.0.1",
            size=11
        )

    def test_home_view(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test File")

    def test_document_detail_view(self):
        response = self.client.get(reverse('document_detail', args=[self.document.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test File")

    def test_upload_document_success(self):
        file = SimpleUploadedFile("upload.txt", b"Some content")
        response = self.client.post(reverse('upload_document'), {'file': file})
        self.assertEqual(response.status_code, 302)  # Redirect to document detail
        self.assertEqual(Document.objects.count(), 2)

    def test_upload_document_no_file(self):
        response = self.client.post(reverse('upload_document'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'documents/upload_error.html')
