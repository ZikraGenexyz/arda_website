from django.contrib import admin
from .models import UserList

# Register your models here.
@admin.register(UserList)
class UserListAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'mood', 'genre', 'created_at')
    search_fields = ('id', 'name', 'mood', 'genre')
    list_filter = ('mood', 'genre')
