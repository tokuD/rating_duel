# Generated by Django 4.0.4 on 2022-05-08 13:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0015_game_submitted_players'),
    ]

    operations = [
        migrations.AddField(
            model_name='leaguecategory',
            name='details',
            field=models.TextField(blank=True, verbose_name='詳細'),
        ),
    ]
