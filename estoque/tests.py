from django.test import TestCase

from .models import Consumivel, Impressora, ModeloImpressora, ModeloToner, Pedido
from .services import calcular_alertas, mudar_status_pedido


def _toner(nome, estoque=0, minimo=3):
    return Consumivel.objects.create(nome=nome, tipo='toner',
                                     estoque_unidade=estoque, estoque_minimo=minimo)


class AlertaETests(TestCase):
    def setUp(self):
        self.toner = _toner('Toner X')
        modelo = ModeloImpressora.objects.create(nome='M1', tipo='laser mono')
        ModeloToner.objects.create(modelo=modelo, cor='preto', consumivel=self.toner)
        self.imp = Impressora.objects.create(nome='I1', modelo=modelo, numero_serie='A1',
                                             localizacao='Sala 1')
        self.nivel = self.imp.niveis.get(cor='preto')

    def test_alerta_com_quantidade_sugerida(self):
        alertas = calcular_alertas()
        self.assertEqual(len(alertas), 1)
        self.assertEqual(alertas[0]['quantidade_sugerida'], 3)
        self.assertFalse(alertas[0]['em_andamento'])

    def test_sem_alerta_se_ha_reserva_na_sala(self):
        self.nivel.na_sala = 1
        self.nivel.save()
        self.assertEqual(calcular_alertas(), [])

    def test_pedido_em_andamento(self):
        Pedido.objects.create(consumivel=self.toner, quantidade=3, solicitante='Ana')
        self.assertTrue(calcular_alertas()[0]['em_andamento'])

    def test_receber_soma_estoque_uma_vez(self):
        p = Pedido.objects.create(consumivel=self.toner, quantidade=3, solicitante='Ana')
        mudar_status_pedido(p.pk, 'recebido')
        mudar_status_pedido(p.pk, 'recebido')
        self.toner.refresh_from_db()
        self.assertEqual(self.toner.estoque_unidade, 3)

    def test_criar_pedido_volta_para_a_pagina_de_origem(self):
        dados = {'consumivel': self.toner.id, 'quantidade': 3, 'solicitante': 'Ana'}
        r = self.client.post('/pedidos/criar/', {**dados, 'voltar': 'painel'})
        self.assertRedirects(r, '/')
        r = self.client.post('/pedidos/criar/', {**dados, 'voltar': 'http://externo.com'})
        self.assertRedirects(r, '/pedidos/')

    def test_paginas_respondem(self):
        self.assertEqual(self.client.get('/').status_code, 200)
        self.assertEqual(self.client.get('/pedidos/').status_code, 200)


class CoresTests(TestCase):
    def setUp(self):
        self.itens = {c: _toner(f'Konica {c}', estoque=5, minimo=2)
                      for c in ('preto', 'ciano', 'magenta', 'amarelo')}
        self.modelo = ModeloImpressora.objects.create(nome='Konica', tipo='laser colorida')
        for cor, item in self.itens.items():
            ModeloToner.objects.create(modelo=self.modelo, cor=cor, consumivel=item)
        self.imp = Impressora.objects.create(nome='K1', modelo=self.modelo, numero_serie='K1',
                                             localizacao='Lab')

    def test_konica_tem_quatro_niveis_e_epson_um(self):
        self.assertEqual(self.imp.niveis.count(), 4)
        epson = ModeloImpressora.objects.create(nome='Epson', tipo='laser mono')
        ModeloToner.objects.create(modelo=epson, cor='preto', consumivel=_toner('Epson preto'))
        e1 = Impressora.objects.create(nome='E1', modelo=epson, numero_serie='E1', localizacao='S2')
        self.assertEqual([n.cor for n in e1.niveis.all()], ['preto'])

    def test_alerta_so_para_a_cor_sem_reserva(self):
        self.imp.niveis.update(na_sala=1)
        self.imp.niveis.filter(cor='ciano').update(na_sala=0)
        self.itens['ciano'].estoque_unidade = 0
        self.itens['ciano'].save()
        alertas = calcular_alertas()
        self.assertEqual([a['consumivel'].nome for a in alertas], ['Konica ciano'])
        self.assertEqual(alertas[0]['afetadas'], ['K1 (Ciano (azul))'])

    def test_adicionar_cor_ao_modelo_cria_nivel_nas_impressoras(self):
        modelo = ModeloImpressora.objects.create(nome='Nova', tipo='mono')
        imp = Impressora.objects.create(nome='N1', modelo=modelo, numero_serie='N1', localizacao='X')
        self.assertEqual(imp.niveis.count(), 0)
        ModeloToner.objects.create(modelo=modelo, cor='preto', consumivel=_toner('Nova preto'))
        self.assertEqual(imp.niveis.count(), 1)

    def test_atualizar_niveis_pela_tela(self):
        dados = {'residuo_na_sala': 0}
        for cor in ('preto', 'ciano', 'magenta', 'amarelo'):
            dados[f'nivel_{cor}'] = 40
            dados[f'sala_{cor}'] = 2
        dados['nivel_ciano'] = 7
        self.client.post(f'/impressoras/{self.imp.id}/atualizar/', dados)
        self.assertEqual(self.imp.niveis.get(cor='ciano').nivel, 7)
        self.assertEqual(self.imp.niveis.get(cor='preto').na_sala, 2)

    def test_nivel_invalido_nao_salva_nada(self):
        dados = {'residuo_na_sala': 0}
        for cor in ('preto', 'ciano', 'magenta', 'amarelo'):
            dados[f'nivel_{cor}'] = 10
            dados[f'sala_{cor}'] = 0
        dados['nivel_amarelo'] = 150
        self.client.post(f'/impressoras/{self.imp.id}/atualizar/', dados)
        self.assertEqual(self.imp.niveis.get(cor='preto').nivel, 100)
