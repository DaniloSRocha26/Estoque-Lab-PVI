import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('estoque', '0003_grupos_de_acesso'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='consumivel',
            name='atualizado_em',
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='niveltoner',
            name='atualizado_em',
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.CreateModel(
            name='Troca',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('impressora_nome', models.CharField(max_length=100)),
                ('cor', models.CharField(choices=[('preto', 'Preto'), ('ciano', 'Ciano (azul)'), ('magenta', 'Magenta'), ('amarelo', 'Amarelo')], max_length=10)),
                ('toner_nome', models.CharField(blank=True, max_length=100)),
                ('nivel_anterior', models.PositiveIntegerField()),
                ('usuario_nome', models.CharField(blank=True, max_length=150)),
                ('registrado_em', models.DateTimeField(auto_now_add=True)),
                ('impressora', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='trocas', to='estoque.impressora')),
                ('toner', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='estoque.consumivel')),
                ('usuario', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'troca de toner',
                'verbose_name_plural': 'trocas de toner',
                'ordering': ['-registrado_em', '-id'],
            },
        ),
    ]
