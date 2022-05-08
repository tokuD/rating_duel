# Generated by Django 4.0.4 on 2022-05-07 12:46

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('game', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='resulttable',
            old_name='league_category',
            new_name='league',
        ),
        migrations.AlterField(
            model_name='leaguecategory',
            name='players',
            field=models.ManyToManyField(blank=True, to=settings.AUTH_USER_MODEL, verbose_name='参加者'),
        ),
        migrations.AlterField(
            model_name='resulttable',
            name='dp',
            field=models.IntegerField(default=0, verbose_name='dp'),
        ),
        migrations.AlterField(
            model_name='resulttable',
            name='game_num',
            field=models.IntegerField(default=0, verbose_name='試合数'),
        ),
        migrations.AlterField(
            model_name='resulttable',
            name='loose',
            field=models.IntegerField(default=0, verbose_name='負け数'),
        ),
        migrations.AlterField(
            model_name='resulttable',
            name='win',
            field=models.IntegerField(default=0, verbose_name='勝ち数'),
        ),
    ]