from rest_framework import serializers
from .models import UserList

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserList
        fields = ['id', 'name', 'mood', 'genre']
    
    def create(self, validated_data):
        user = UserList.objects.create(
            name=validated_data['name'],
            mood=validated_data['mood'],
            genre=validated_data['genre']
        )
        return user 