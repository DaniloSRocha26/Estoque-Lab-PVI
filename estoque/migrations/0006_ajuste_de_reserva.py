import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('estoque', '0005_origem_da_troca_e_reposicoes'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AjusteReserva',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('impressora_nome', models.CharField(max_length=100)),
                ('descricao', models.CharField(max_length=100)),
                ('cor', models.CharField(blank=True, choices=[('preto', 'Preto'), ('ciano', 'Ciano (azul)'), ('magenta', 'Magenta'), ('amarelo', 'Amarelo')], max_length=10)),
                ('anterior', models.PositiveIntegerField()),
                ('novo', models.PositiveIntegerField()),
                ('usuario_nome', models.CharField(blank=True, max_length=150)),
                ('registrado_em', models.DateTimeField(auto_now_add=True)),
                ('impressora', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ajustes', to='estoque.impressora')),
                ('usuario', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'ajuste de contagem',
                'verbose_name_plural': 'ajustes de contagem',
                'ordering': ['-registrado_em', '-id'],
            },
        ),
    ]
