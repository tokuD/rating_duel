# Generated by Django 4.0.4 on 2022-05-08 13:36

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('game', '0016_leaguecategory_details'),
    ]

    operations = [
        migrations.AddField(
            model_name='leaguecategory',
            name='host',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.PROTECT, related_name='league_category', to=settings.AUTH_USER_MODEL, verbose_name='主催者'),
        ),
    ]