import django.db.models.deletion
import arda_app.models
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='UserList',
            fields=[
                ('id', models.CharField(default=arda_app.models.generate_unique_id, max_length=28, primary_key=True, serialize=False, unique=True)),
                ('name', models.CharField(max_length=255)),
                ('mood', models.CharField(max_length=255)),
                ('genre', models.CharField(max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]