from django.db import migrations


def criar_grupos(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    for nome in ('admin', 'visualizador'):
        Group.objects.get_or_create(name=nome)


class Migration(migrations.Migration):

    dependencies = [
        ('estoque', '0002_toner_por_cor'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(criar_grupos, migrations.RunPython.noop),
    ]
