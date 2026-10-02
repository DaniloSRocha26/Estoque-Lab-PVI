from django.core.management.base import BaseCommand
from django.db import transaction

from estoque.models import Consumivel, Impressora, ModeloImpressora, ModeloToner, Pedido


class Command(BaseCommand):
    help = ('Carrega dados fictícios (Konica colorida e Epson preto e branco) para testar o painel. '
            'Use --limpar para apagar tudo antes.')

    def add_arguments(self, parser):
        parser.add_argument('--limpar', action='store_true',
                            help='Apaga impressoras, modelos, consumíveis e pedidos antes de carregar.')

    @transaction.atomic
    def handle(self, *args, **options):
        if options['limpar']:
            Pedido.objects.all().delete()
            Impressora.objects.all().delete()
            ModeloImpressora.objects.all().delete()
            Consumivel.objects.all().delete()
        elif Consumivel.objects.exists():
            self.stdout.write('Já existem dados; use --limpar para recarregar.')
            return

        def toner(nome, estoque, minimo):
            return Consumivel.objects.create(nome=nome, tipo='toner',
                                             estoque_unidade=estoque, estoque_minimo=minimo)

        konica = {
            'preto': toner('Konica Toner Preto', 2, 2),
            'ciano': toner('Konica Toner Ciano', 0, 2),
            'magenta': toner('Konica Toner Magenta', 1, 2),
            'amarelo': toner('Konica Toner Amarelo', 3, 2),
        }
        epson_preto = toner('Epson Toner Preto', 5, 2)
        residuo_konica = Consumivel.objects.create(nome='Konica Caixa de resíduo',
                                                   tipo='residuo', estoque_unidade=1, estoque_minimo=2)

        modelo_konica = ModeloImpressora.objects.create(nome='Konica Minolta', tipo='laser colorida',
                                                        caixa_residuo=residuo_konica)
        modelo_epson = ModeloImpressora.objects.create(nome='Epson', tipo='laser mono')
        for cor, item in konica.items():
            ModeloToner.objects.create(modelo=modelo_konica, cor=cor, consumivel=item)
        ModeloToner.objects.create(modelo=modelo_epson, cor='preto', consumivel=epson_preto)

        def definir(impressora, **niveis):
            for linha in impressora.niveis.all():
                nivel, na_sala = niveis.get(linha.cor, (100, 1))
                linha.nivel, linha.na_sala = nivel, na_sala
                linha.save()

        k1 = Impressora.objects.create(nome='Konica Recepção', modelo=modelo_konica,
                                       numero_serie='KON-001', localizacao='Recepção',
                                       residuo_na_sala=0)
        definir(k1, preto=(70, 1), ciano=(8, 0), magenta=(35, 1), amarelo=(90, 1))
        k2 = Impressora.objects.create(nome='Konica Laboratório', modelo=modelo_konica,
                                       numero_serie='KON-002', localizacao='Laboratório',
                                       residuo_na_sala=1)
        definir(k2, preto=(55, 1), ciano=(60, 1), magenta=(48, 1), amarelo=(80, 1))
        e1 = Impressora.objects.create(nome='Epson Sala 2', modelo=modelo_epson,
                                       numero_serie='EPS-001', localizacao='Sala 2')
        definir(e1, preto=(12, 0))
        e2 = Impressora.objects.create(nome='Epson Secretaria', modelo=modelo_epson,
                                       numero_serie='EPS-002', localizacao='Secretaria')
        definir(e2, preto=(85, 2))

        self.stdout.write(self.style.SUCCESS('Dados de exemplo carregados.'))
