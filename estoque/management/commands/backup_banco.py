import sqlite3

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

MANTER = 10  # quantas cópias guardar; as mais antigas são apagadas


class Command(BaseCommand):
    help = (f'Faz uma cópia do banco em backups/ (com data e hora) e mantém as {MANTER} mais recentes. '
            'Pode rodar com o site no ar.')

    def handle(self, *args, **o):
        banco = settings.DATABASES['default']
        if banco['ENGINE'] != 'django.db.backends.sqlite3':
            raise CommandError('Este comando só copia banco SQLite.')
        pasta = settings.BASE_DIR / 'backups'
        pasta.mkdir(exist_ok=True)
        destino = pasta / f'banco-{timezone.localtime():%Y-%m-%d-%H%M%S}.sqlite3'

        # a cópia pela própria SQLite fica consistente mesmo se alguém salvar algo durante o backup
        origem = sqlite3.connect(banco['NAME'])
        copia = sqlite3.connect(destino)
        with copia:
            origem.backup(copia)
        copia.close()
        origem.close()

        for antigo in sorted(pasta.glob('banco-*.sqlite3'))[:-MANTER]:
            antigo.unlink()
        self.stdout.write(self.style.SUCCESS(f'Backup salvo em {destino}'))
