from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.management.utils import get_random_secret_key


class Command(BaseCommand):
    help = ('Cria o arquivo .env do servidor com uma chave secreta nova, DEBUG desligado e o endereço '
            'do site. Ex.: preparar_producao --host danilo.pythonanywhere.com')

    def add_arguments(self, parser):
        parser.add_argument('--host', required=True,
                            help='Endereço do site, sem https:// (ex.: danilo.pythonanywhere.com).')

    def handle(self, *args, **o):
        host = o['host'].strip().removeprefix('https://').removeprefix('http://').strip('/')
        if not host or '/' in host:
            raise CommandError('Informe só o endereço, ex.: --host danilo.pythonanywhere.com')
        arquivo = settings.BASE_DIR / '.env'
        if arquivo.exists():  # trocar a chave derruba as sessões abertas: só de propósito
            raise CommandError(f'{arquivo} já existe. Apague-o antes se quiser gerar de novo.')
        arquivo.write_text(
            '# Configuração do servidor. Não envie este arquivo para o GitHub.\n'
            f'DJANGO_SECRET_KEY={get_random_secret_key()}\n'
            'DJANGO_DEBUG=0\n'
            f'DJANGO_ALLOWED_HOSTS={host}\n', encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(f'Arquivo {arquivo} criado para {host}.'))
