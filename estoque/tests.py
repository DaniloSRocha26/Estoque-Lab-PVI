from django.test import TestCase

from .models import Consumivel, Impressora, ModeloImpressora, Pedido
from .services import calcular_alertas, mudar_status_pedido


class AlertaETests(TestCase):
    def setUp(self):
        self.toner = Consumivel.objects.create(nome='Toner X', tipo='toner',
                                               estoque_unidade=0, estoque_minimo=3)
        modelo = ModeloImpressora.objects.create(nome='M1', tipo='laser mono', toner=self.toner)
        self.imp = Impressora.objects.create(nome='I1', modelo=modelo, numero_serie='A1',
                                             localizacao='Sala 1', toner_na_sala=0)

    def test_alerta_com_quantidade_sugerida(self):
        alertas = calcular_alertas()
        self.assertEqual(len(alertas), 1)
        self.assertEqual(alertas[0]['quantidade_sugerida'], 3)
        self.assertFalse(alertas[0]['em_andamento'])

    def test_sem_alerta_se_ha_reserva_na_sala(self):
        self.imp.toner_na_sala = 1
        self.imp.save()
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

    def test_paginas_respondem(self):
        self.assertEqual(self.client.get('/').status_code, 200)
        self.assertEqual(self.client.get('/pedidos/').status_code, 200)
