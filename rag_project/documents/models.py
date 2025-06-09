from django.db import models

class Document(models.Model):
    title = models.CharField(max_length=255, blank=True)
    # id_hash = models.CharField(max_length=64, unique=True, blank=True)
    file = models.FileField(upload_to='docs/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.CharField(max_length=255, blank=True)
    raw_bytes = models.BinaryField(blank=True, null=True)
    size = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.title or self.file.name


