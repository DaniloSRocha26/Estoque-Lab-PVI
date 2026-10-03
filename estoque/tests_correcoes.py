from django.contrib import admin
from django.db import IntegrityError, transaction
from django.test import RequestFactory

from .models import (AjusteEstoque, AjusteReserva, Consumivel, Impressora, ModeloImpressora,
                     NivelToner, Pedido, Reposicao, Troca)
from .services import calcular_alertas, mudar_status_pedido
from .tests import NovasFuncoesBase, TestCase, _toner


class SalvarCardSemApagarMudancaDeOutroTests(NovasFuncoesBase):
    """O card envia o que estava na tela (orig_*); o servidor só grava o que a pessoa mudou."""

    def _salvar(self, nivel, sala, orig_nivel, orig_sala):
        return self.client.post(f'/impressoras/{self.imp.id}/atualizar/', {
            'nivel_ciano': nivel, 'sala_ciano': sala, 'residuo_na_sala': 0,
            'orig_nivel_ciano': orig_nivel, 'orig_sala_ciano': orig_sala, 'orig_residuo_na_sala': 0,
        }, follow=True)

    def test_reposicao_feita_por_outro_nao_e_desfeita(self):
        self._definir(40, na_sala=0)
        self.nivel.na_sala = 1  # outra pessoa repôs a sala enquanto o card estava aberto
        self.nivel.save()
        self._salvar(nivel=30, sala=0, orig_nivel=40, orig_sala=0)  # só mexeu no nível
        self.nivel.refresh_from_db()
        self.assertEqual((self.nivel.nivel, self.nivel.na_sala), (30, 1))
        self.assertEqual(AjusteReserva.objects.count(), 0)

    def test_troca_feita_por_outro_nao_volta_o_nivel(self):
        self._definir(10, na_sala=2)
        self.client.post(f'/impressoras/{self.imp.id}/trocar/ciano/')  # nível vai a 100
        self._salvar(nivel=10, sala=2, orig_nivel=10, orig_sala=2)  # card antigo, sem mudança
        self.nivel.refresh_from_db()
        self.assertEqual((self.nivel.nivel, self.nivel.na_sala), (100, 1))

    def test_os_dois_mudaram_o_mesmo_numero_recusa(self):
        self._definir(40, na_sala=0)
        self.nivel.na_sala = 1
        self.nivel.save()
        r = self._salvar(nivel=40, sala=3, orig_nivel=40, orig_sala=0)
        self.assertContains(r, 'Outra pessoa mudou a K1')
        self.nivel.refresh_from_db()
        self.assertEqual(self.nivel.na_sala, 1)
        self.assertEqual(AjusteReserva.objects.count(), 0)

    def test_mudanca_propria_continua_registrada(self):
        self._definir(40, na_sala=0)
        self._salvar(nivel=40, sala=2, orig_nivel=40, orig_sala=0)
        self.nivel.refresh_from_db()
        self.assertEqual(self.nivel.na_sala, 2)
        self.assertEqual(AjusteReserva.objects.get().novo, 2)

    def test_card_envia_os_valores_originais(self):
        self._definir(40, na_sala=2)
        r = self.client.get('/impressoras/')
        self.assertContains(r, 'name="orig_nivel_ciano" value="40"')
        self.assertContains(r, 'name="orig_sala_ciano" value="2"')


class AjusteDeEstoqueTests(NovasFuncoesBase):
    def test_ajuste_pela_tela_fica_no_historico(self):
        self.client.post(f'/consumiveis/{self.toner.id}/atualizar/',
                         {'estoque_unidade': 8, 'orig_estoque_unidade': 5})
        ajuste = AjusteEstoque.objects.get()
        self.assertEqual((ajuste.item_nome, ajuste.anterior, ajuste.novo, ajuste.usuario_nome),
                         ('Konica Toner Ciano', 5, 8, 'admin_teste'))
        r = self.client.get('/historico/')
        self.assertContains(r, 'Ajustes de estoque')
        self.assertEqual(list(r.context['ajustes_estoque']), [ajuste])

    def test_salvar_sem_mudar_nao_registra(self):
        self.client.post(f'/consumiveis/{self.toner.id}/atualizar/',
                         {'estoque_unidade': 5, 'orig_estoque_unidade': 5})
        self.assertEqual(AjusteEstoque.objects.count(), 0)

    def test_estoque_mudou_enquanto_editava_recusa(self):
        Consumivel.objects.filter(pk=self.toner.pk).update(estoque_unidade=9)  # pedido recebido
        r = self.client.post(f'/consumiveis/{self.toner.id}/atualizar/',
                             {'estoque_unidade': 4, 'orig_estoque_unidade': 5}, follow=True)
        self.assertContains(r, 'Outra pessoa mudou o estoque')
        self.toner.refresh_from_db()
        self.assertEqual(self.toner.estoque_unidade, 9)

    def test_edicao_em_cadastros_tambem_registra(self):
        self.client.post(f'/cadastros/itens/{self.toner.id}/editar/', {
            'nome': 'Konica Toner Ciano', 'estoque_unidade': 2, 'estoque_minimo': 4,
            'orig_estoque_unidade': 5})
        self.toner.refresh_from_db()
        self.assertEqual((self.toner.estoque_unidade, self.toner.estoque_minimo), (2, 4))
        self.assertEqual((AjusteEstoque.objects.get().anterior, AjusteEstoque.objects.get().novo), (5, 2))


class PedidoCanceladoTests(NovasFuncoesBase):
    def setUp(self):
        super().setUp()
        self.pedido = Pedido.objects.create(consumivel=self.toner, quantidade=3, solicitante='Ana')

    def test_cancelado_e_final_e_nao_soma_no_estoque(self):
        self.client.post(f'/pedidos/{self.pedido.id}/status/', {'status': 'cancelado'})
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.status, 'cancelado')
        self.assertEqual(self.pedido.finalizado_por, 'admin_teste')
        self.assertIsNotNone(self.pedido.finalizado_em)
        mudar_status_pedido(self.pedido.pk, 'recebido')
        self.pedido.refresh_from_db()
        self.toner.refresh_from_db()
        self.assertEqual((self.pedido.status, self.toner.estoque_unidade), ('cancelado', 5))

    def test_cancelado_nao_esconde_o_alerta(self):
        Consumivel.objects.filter(pk=self.toner.pk).update(estoque_unidade=0)
        self._definir(10, na_sala=0)
        self.assertTrue(calcular_alertas()[0]['em_andamento'])
        mudar_status_pedido(self.pedido.pk, 'cancelado')
        self.assertFalse(calcular_alertas()[0]['em_andamento'])

    def test_recebido_guarda_quando_e_quem(self):
        self.client.post(f'/pedidos/{self.pedido.id}/status/', {'status': 'recebido'})
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.finalizado_por, 'admin_teste')
        self.assertContains(self.client.get('/pedidos/'), 'admin_teste')

    def test_pagina_separa_a_caminho_e_finalizados(self):
        recebido = Pedido.objects.create(consumivel=self.toner, quantidade=1, solicitante='Bia')
        mudar_status_pedido(recebido.pk, 'recebido')
        r = self.client.get('/pedidos/')
        self.assertEqual(list(r.context['a_caminho']), [self.pedido])
        self.assertEqual(list(r.context['finalizados']), [recebido])
        self.assertContains(r, 'name="status" value="recebido"')

    def test_pedido_inexistente_da_404(self):
        self.assertEqual(self.client.post('/pedidos/999999/status/', {'status': 'enviado'}).status_code, 404)


class QuantidadeSugeridaTests(TestCase):
    def setUp(self):
        super().setUp()
        self.toner = _toner('Toner X', estoque=1, minimo=2)
        modelo = ModeloImpressora.objects.create(nome='M1', tipo='laser mono')
        modelo.toners.create(cor='preto', consumivel=self.toner)
        for n in range(3):  # 3 salas sem reserva
            modelo.impressora_set.create(nome=f'I{n}', numero_serie=f'S{n}', localizacao='Sala')

    def _alerta(self):
        return calcular_alertas()[0]

    def test_cobre_as_salas_e_o_minimo(self):
        self.assertEqual(self._alerta()['quantidade_sugerida'], 4)  # 2 + 3 salas - 1 em estoque

    def test_pedido_que_nao_basta_pede_o_resto(self):
        Pedido.objects.create(consumivel=self.toner, quantidade=1, solicitante='Ana')
        alerta = self._alerta()
        self.assertEqual((alerta['em_andamento'], alerta['pedido_cobre'], alerta['quantidade_sugerida']),
                         (True, False, 3))
        self.assertContains(self.client.get('/'), 'name="quantidade" min="1" value="3"')

    def test_pedido_que_basta_mostra_aguardando(self):
        Pedido.objects.create(consumivel=self.toner, quantidade=4, solicitante='Ana')
        self.assertTrue(self._alerta()['pedido_cobre'])
        self.assertContains(self.client.get('/'), 'Pedido já feito, aguardando chegar')


class AdminProtegeHistoricoTests(NovasFuncoesBase):
    def test_historico_e_somente_leitura_no_admin(self):
        request = RequestFactory().get('/')
        request.user = self.admin
        for modelo in (Troca, Reposicao, AjusteReserva, AjusteEstoque):
            modelo_admin = admin.site._registry[modelo]
            self.assertFalse(modelo_admin.has_change_permission(request), modelo)
            self.assertFalse(modelo_admin.has_delete_permission(request), modelo)

    def test_estoque_e_status_nao_mudam_pelo_admin(self):
        request = RequestFactory().get('/')
        request.user = self.admin
        self.assertIn('estoque_unidade', admin.site._registry[Consumivel].get_readonly_fields(request, self.toner))
        self.assertNotIn('estoque_unidade', admin.site._registry[Consumivel].get_readonly_fields(request))
        self.assertIn('status', admin.site._registry[Pedido].get_readonly_fields(request))


class NivelAte100Tests(NovasFuncoesBase):
    def test_banco_recusa_nivel_acima_de_100(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            NivelToner.objects.filter(pk=self.nivel.pk).update(nivel=150)


class NomeRepetidoTests(TestCase):
    def test_modelo_e_item_com_nome_repetido_sao_recusados(self):
        ModeloImpressora.objects.create(nome='Konica', tipo='laser mono')
        self.client.post('/cadastros/modelos/criar/', {'nome': 'konica', 'tipo': 'mono', 'estoque_minimo': 2})
        self.assertEqual(ModeloImpressora.objects.count(), 1)
        _toner('Toner A')
        self.client.post('/cadastros/itens/criar/', {'nome': 'TONER A', 'tipo': 'toner',
                                                      'estoque_unidade': 0, 'estoque_minimo': 1})
        self.assertEqual(Consumivel.objects.filter(nome__iexact='toner a').count(), 1)

    def test_renomear_para_o_proprio_nome_funciona(self):
        item = _toner('Toner A', estoque=2)
        self.client.post(f'/cadastros/itens/{item.id}/editar/', {
            'nome': 'Toner A', 'estoque_unidade': 2, 'estoque_minimo': 5, 'orig_estoque_unidade': 2})
        item.refresh_from_db()
        self.assertEqual(item.estoque_minimo, 5)


class TrocarModeloDevolveAoEstoqueTests(TestCase):
    """Konica (4 cores + resíduo) trocada por Epson (só preto, sem resíduo)."""

    def setUp(self):
        super().setUp()
        self.residuo = Consumivel.objects.create(nome='Konica resíduo', tipo='residuo', estoque_unidade=0)
        self.konica = ModeloImpressora.objects.create(nome='Konica', tipo='laser colorida',
                                                      caixa_residuo=self.residuo)
        self.itens = {c: _toner(f'Konica {c}') for c in ('preto', 'ciano', 'magenta', 'amarelo')}
        for cor, item in self.itens.items():
            self.konica.toners.create(cor=cor, consumivel=item)
        self.epson_preto = _toner('Epson preto')
        self.epson = ModeloImpressora.objects.create(nome='Epson', tipo='laser mono')
        self.epson.toners.create(cor='preto', consumivel=self.epson_preto)
        self.imp = Impressora.objects.create(nome='Recepção', modelo=self.konica, numero_serie='S1',
                                             localizacao='Recepção', residuo_na_sala=1)
        self.imp.niveis.update(na_sala=1, nivel=40)
        self.imp.niveis.filter(cor='ciano').update(na_sala=2)

    def _trocar_para(self, modelo):
        return self.client.post(f'/cadastros/impressoras/{self.imp.id}/editar/', {
            'nome': 'Recepção', 'modelo': modelo.id, 'numero_serie': 'S1', 'localizacao': 'Recepção'},
            follow=True)

    def _estoque(self, item):
        item.refresh_from_db()
        return item.estoque_unidade

    def test_reserva_que_nao_serve_volta_ao_estoque(self):
        r = self._trocar_para(self.epson)
        self.assertEqual([self._estoque(self.itens[c]) for c in ('preto', 'ciano', 'magenta', 'amarelo')],
                         [1, 2, 1, 1])
        self.assertEqual(self._estoque(self.residuo), 1)
        self.assertEqual(self._estoque(self.epson_preto), 0)
        self.imp.refresh_from_db()
        preto = self.imp.niveis.get()
        self.assertEqual((preto.cor, preto.nivel, preto.na_sala, self.imp.residuo_na_sala),
                         ('preto', 100, 0, 0))
        self.assertContains(r, 'Voltaram ao estoque')

    def test_devolucao_fica_no_historico(self):
        self._trocar_para(self.epson)
        self.assertEqual(AjusteEstoque.objects.count(), 5)  # 4 toners + caixa de resíduo
        self.assertTrue(all('Konica para Epson' in a.motivo for a in AjusteEstoque.objects.all()))
        self.assertEqual(AjusteReserva.objects.filter(novo=0).count(), 5)
        self.assertContains(self.client.get('/historico/'), 'modelo trocado de Konica para Epson')

    def test_mesmo_toner_no_modelo_novo_mantem_a_reserva(self):
        konica_nova = ModeloImpressora.objects.create(nome='Konica nova', tipo='laser colorida',
                                                      caixa_residuo=self.residuo)
        for cor, item in self.itens.items():
            konica_nova.toners.create(cor=cor, consumivel=item)
        self._trocar_para(konica_nova)
        self.assertEqual(AjusteEstoque.objects.count(), 0)
        self.imp.refresh_from_db()
        self.assertEqual(self.imp.niveis.get(cor='ciano').na_sala, 2)
        self.assertEqual(self.imp.residuo_na_sala, 1)

    def test_salvar_sem_trocar_o_modelo_nao_mexe_em_nada(self):
        self._trocar_para(self.konica)
        self.assertEqual(AjusteEstoque.objects.count(), 0)
        self.assertEqual(self.imp.niveis.get(cor='ciano').na_sala, 2)

    def test_tela_pede_confirmacao_ao_trocar_o_modelo(self):
        self.assertContains(self.client.get('/cadastros/'), 'data-confirmar-modelo=')
