from django.db import models
import string
import secrets

# Create your models here.

def generate_unique_id(length=28):
    characters = string.ascii_letters + string.digits  # A-Z, a-z, 0-9
    return ''.join(secrets.choice(characters) for _ in range(length))

class UserList(models.Model):
    id = models.CharField(max_length=28, unique=True, default=generate_unique_id, primary_key=True)
    name = models.CharField(max_length=255)
    mood = models.CharField(max_length=255)
    genre = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = generate_unique_id()
        super().save(*args, **kwargs)