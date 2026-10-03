import sqlite3
import tempfile
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from config.settings import _carregar_env


class PrepararProducaoTests(SimpleTestCase):
    def setUp(self):
        self.pasta = Path(tempfile.mkdtemp())

    def test_cria_env_com_chave_nova_e_host(self):
        with override_settings(BASE_DIR=self.pasta):
            call_command('preparar_producao', host='https://danilo.pythonanywhere.com/', stdout=mock.Mock())
        texto = (self.pasta / '.env').read_text(encoding='utf-8')
        self.assertIn('DJANGO_DEBUG=0', texto)
        self.assertIn('DJANGO_ALLOWED_HOSTS=danilo.pythonanywhere.com\n', texto)
        chave = next(l for l in texto.splitlines() if l.startswith('DJANGO_SECRET_KEY='))
        self.assertGreater(len(chave), 60)
        self.assertNotIn('django-insecure', chave)

    def test_nao_sobrescreve_env_existente(self):
        (self.pasta / '.env').write_text('DJANGO_SECRET_KEY=antiga\n', encoding='utf-8')
        with override_settings(BASE_DIR=self.pasta), self.assertRaises(CommandError):
            call_command('preparar_producao', host='x.pythonanywhere.com')
        self.assertEqual((self.pasta / '.env').read_text(encoding='utf-8'), 'DJANGO_SECRET_KEY=antiga\n')

    def test_settings_le_o_env_sem_sobrescrever_o_ambiente(self):
        arquivo = self.pasta / '.env'
        arquivo.write_text('# comentário\nTESTE_ENV_A=1\nTESTE_ENV_B = com=igual\n', encoding='utf-8')
        with mock.patch.dict('os.environ', {'TESTE_ENV_A': 'do ambiente'}, clear=False):
            _carregar_env(arquivo)
            import os
            self.assertEqual(os.environ['TESTE_ENV_A'], 'do ambiente')
            self.assertEqual(os.environ['TESTE_ENV_B'], 'com=igual')


class BackupBancoTests(SimpleTestCase):
    def test_copia_o_banco_e_mantem_as_mais_recentes(self):
        pasta = Path(tempfile.mkdtemp())
        banco = pasta / 'db.sqlite3'
        with sqlite3.connect(banco) as c:
            c.execute('create table t (x)')
            c.execute("insert into t values ('ok')")
        (pasta / 'backups').mkdir()
        for n in range(12):  # cópias antigas
            (pasta / 'backups' / f'banco-2000-01-{n + 1:02d}-000000.sqlite3').write_bytes(b'')
        bancos = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': str(banco)}}
        with mock.patch('django.conf.settings.DATABASES', bancos), override_settings(BASE_DIR=pasta):
            call_command('backup_banco', stdout=mock.Mock())
        copias = sorted((pasta / 'backups').glob('banco-*.sqlite3'))
        self.assertEqual(len(copias), 10)
        with sqlite3.connect(copias[-1]) as c:
            self.assertEqual(c.execute('select x from t').fetchall(), [('ok',)])
