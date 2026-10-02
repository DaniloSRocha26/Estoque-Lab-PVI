from django.contrib.auth.models import Group, User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from estoque.acesso import GRUPO_ADMIN, GRUPO_VISUALIZADOR


class Command(BaseCommand):
    help = 'Cria um usuário do sistema: criar_usuario NOME --perfil admin|visualizador --senha SENHA'

    def add_arguments(self, parser):
        parser.add_argument('username')
        parser.add_argument('--perfil', choices=[GRUPO_ADMIN, GRUPO_VISUALIZADOR], default=GRUPO_ADMIN)
        parser.add_argument('--senha', required=True)
        parser.add_argument('--nome', default='')

    def handle(self, *args, **o):
        if User.objects.filter(username=o['username']).exists():
            raise CommandError('Esse usuário já existe.')
        try:
            validate_password(o['senha'])
        except ValidationError as e:
            raise CommandError(' '.join(e.messages))
        user = User.objects.create_user(o['username'], password=o['senha'], first_name=o['nome'])
        user.groups.add(Group.objects.get(name=o['perfil']))
        self.stdout.write(self.style.SUCCESS(f'Usuário {user.username} criado como {o["perfil"]}.'))
