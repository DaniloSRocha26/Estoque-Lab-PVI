import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('estoque', '0004_historico_e_atualizacao'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='troca',
            name='origem',
            field=models.CharField(choices=[('sala', 'Reserva da sala'), ('estoque', 'Estoque da unidade')], default='sala', max_length=7),
        ),
        migrations.CreateModel(
            name='Reposicao',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('impressora_nome', models.CharField(max_length=100)),
                ('cor', models.CharField(blank=True, choices=[('preto', 'Preto'), ('ciano', 'Ciano (azul)'), ('magenta', 'Magenta'), ('amarelo', 'Amarelo')], max_length=10)),
                ('item_nome', models.CharField(max_length=100)),
                ('quantidade', models.PositiveIntegerField()),
                ('usuario_nome', models.CharField(blank=True, max_length=150)),
                ('registrado_em', models.DateTimeField(auto_now_add=True)),
                ('impressora', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reposicoes', to='estoque.impressora')),
                ('item', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='estoque.consumivel')),
                ('usuario', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'reposição na sala',
                'verbose_name_plural': 'reposições na sala',
                'ordering': ['-registrado_em', '-id'],
            },
        ),
    ]
