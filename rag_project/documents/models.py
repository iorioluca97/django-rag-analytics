from django.db import models

class Document(models.Model):
    title = models.CharField(max_length=255, blank=True)
    file = models.FileField(upload_to='docs/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.CharField(max_length=255, blank=True)
    raw_bytes = models.BinaryField(blank=True, null=True)
    size = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.title or self.file.name
    
class DocumentImage(models.Model):
    document = models.ForeignKey(Document, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='images/')
    page_number = models.PositiveIntegerField()
    extracted_at = models.DateTimeField(auto_now_add=True)

class Entity(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE)
    text = models.CharField(max_length=255)
    label = models.CharField(max_length=50)  # Es: 'PER', 'ORG', 'LOC'
    start_pos = models.IntegerField()  # Posizione nel testo
    end_pos = models.IntegerField()
