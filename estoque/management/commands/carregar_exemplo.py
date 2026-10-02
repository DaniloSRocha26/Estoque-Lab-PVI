from django.core.management.base import BaseCommand

from estoque.models import Consumivel, Impressora, ModeloImpressora


class Command(BaseCommand):
    help = 'Carrega dados fictícios para testar o painel (não duplica se já existirem).'

    def handle(self, *args, **options):
        if Consumivel.objects.exists():
            self.stdout.write('Já existem dados; nada foi carregado.')
            return

        toner_a = Consumivel.objects.create(nome='Toner A (exemplo)', tipo='toner',
                                            estoque_unidade=0, estoque_minimo=3)
        toner_b = Consumivel.objects.create(nome='Toner B (exemplo)', tipo='toner',
                                            estoque_unidade=5, estoque_minimo=2)
        residuo = Consumivel.objects.create(nome='Caixa de resíduo A (exemplo)', tipo='residuo',
                                            estoque_unidade=1, estoque_minimo=2)

        modelo_a = ModeloImpressora.objects.create(nome='Modelo A', tipo='laser mono',
                                                   toner=toner_a, caixa_residuo=residuo)
        modelo_b = ModeloImpressora.objects.create(nome='Modelo B', tipo='laser colorida',
                                                   toner=toner_b)

        Impressora.objects.create(nome='Impressora Recepção', modelo=modelo_a, numero_serie='EX-001',
                                  localizacao='Recepção', nivel_toner=10,
                                  toner_na_sala=0, residuo_na_sala=0)
        Impressora.objects.create(nome='Impressora Sala 2', modelo=modelo_a, numero_serie='EX-002',
                                  localizacao='Sala 2', nivel_toner=55,
                                  toner_na_sala=1, residuo_na_sala=1)
        Impressora.objects.create(nome='Impressora Laboratório', modelo=modelo_b, numero_serie='EX-003',
                                  localizacao='Laboratório', nivel_toner=90,
                                  toner_na_sala=1, residuo_na_sala=0)
        self.stdout.write(self.style.SUCCESS('Dados de exemplo carregados.'))
