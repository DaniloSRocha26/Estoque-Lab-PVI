from .models import (AjusteReserva, Consumivel, Impressora, ModeloImpressora, ModeloToner,
                     Reposicao, Troca)
from .tests import NovasFuncoesBase, TestCase, _toner, _usuario


class SalasParaReabastecerTests(TestCase):
    """Konica com 4 cores; reserva ideal = 1 de cada."""

    def setUp(self):
        super().setUp()
        self.itens = {c: _toner(f'Konica {c}', estoque=3, minimo=2)
                      for c in ('preto', 'ciano', 'magenta', 'amarelo')}
        self.residuo = Consumivel.objects.create(nome='Konica resíduo', tipo='residuo',
                                                 estoque_unidade=2, estoque_minimo=1)
        modelo = ModeloImpressora.objects.create(nome='Konica', tipo='laser colorida',
                                                 caixa_residuo=self.residuo)
        for cor, item in self.itens.items():
            ModeloToner.objects.create(modelo=modelo, cor=cor, consumivel=item)
        self.imp = Impressora.objects.create(nome='K1', modelo=modelo, numero_serie='S1',
                                             localizacao='Recepção', residuo_na_sala=1)
        self.imp.niveis.update(na_sala=0)
        self.imp.niveis.filter(cor='preto').update(na_sala=1)  # só o preto tem reserva

    def _linha(self, cor):
        return self.imp.niveis.get(cor=cor)

    def test_lista_so_tem_as_cores_sem_reserva(self):
        r = self.client.get('/')
        itens = [(l['tipo'], l['cor']) for l in r.context['reabastecer']]
        self.assertEqual(itens, [('toner', 'ciano'), ('toner', 'magenta'), ('toner', 'amarelo')])
        self.assertEqual(r.context['resumo']['reabastecer'], 3)

    def test_caixa_de_residuo_entra_na_lista(self):
        self.imp.residuo_na_sala = 0
        self.imp.save()
        tipos = [l['tipo'] for l in self.client.get('/').context['reabastecer']]
        self.assertIn('residuo', tipos)

    def test_repor_move_do_estoque_para_a_sala(self):
        self.client.post(f'/impressoras/{self.imp.id}/repor/ciano/')
        self.assertEqual(self._linha('ciano').na_sala, 1)
        self.itens['ciano'].refresh_from_db()
        self.assertEqual(self.itens['ciano'].estoque_unidade, 2)
        rep = Reposicao.objects.get()
        self.assertEqual((rep.cor, rep.quantidade, rep.item_nome), ('ciano', 1, 'Konica ciano'))

    def test_repor_quem_ja_tem_reserva_nao_mexe_no_estoque(self):
        self.client.post(f'/impressoras/{self.imp.id}/repor/preto/')
        self.itens['preto'].refresh_from_db()
        self.assertEqual(self.itens['preto'].estoque_unidade, 3)
        self.assertEqual(Reposicao.objects.count(), 0)

    def test_repor_sem_estoque_recusa(self):
        self.itens['ciano'].estoque_unidade = 0
        self.itens['ciano'].save()
        self.client.post(f'/impressoras/{self.imp.id}/repor/ciano/')
        self.assertEqual(self._linha('ciano').na_sala, 0)
        self.assertEqual(Reposicao.objects.count(), 0)

    def test_repor_residuo(self):
        self.imp.residuo_na_sala = 0
        self.imp.save()
        self.client.post(f'/impressoras/{self.imp.id}/repor/residuo/')
        self.imp.refresh_from_db()
        self.residuo.refresh_from_db()
        self.assertEqual((self.imp.residuo_na_sala, self.residuo.estoque_unidade), (1, 1))

    def test_repor_tudo_repoe_o_que_da_e_deixa_o_resto_na_lista(self):
        self.itens['ciano'].estoque_unidade = 0  # sem ciano no estoque
        self.itens['ciano'].save()
        self.client.post('/reposicao/tudo/')
        self.assertEqual(self._linha('ciano').na_sala, 0)
        self.assertEqual(self._linha('magenta').na_sala, 1)
        self.assertEqual(self._linha('amarelo').na_sala, 1)
        self.assertEqual(self._linha('preto').na_sala, 1)  # nada a repor
        restantes = self.client.get('/').context['reabastecer']
        self.assertEqual([l['cor'] for l in restantes], ['ciano'])
        self.assertFalse(restantes[0]['cobre'])

    def test_tela_mostra_botoes_so_para_admin(self):
        self.assertContains(self.client.get('/'), 'Repor tudo')
        self.client.logout()
        r = self.client.get('/')
        self.assertContains(r, 'Salas para reabastecer')
        self.assertNotContains(r, 'Repor tudo')
        self.assertNotContains(r, 'data-ajax')

    def test_aviso_geral_menciona_salas_sem_reserva(self):
        self.assertContains(self.client.get('/impressoras/'), 'sem reserva nas salas')

    def test_link_do_aviso_leva_direto_para_a_secao(self):
        r = self.client.get('/impressoras/')
        self.assertContains(r, 'href="/#salas-reabastecer"')
        self.assertContains(self.client.get('/'), 'id="salas-reabastecer"')

    def test_sem_aviso_de_atualizacao_no_rodape(self):
        self.assertNotContains(self.client.get('/'), 'se atualiza sozinha')
        self.assertContains(self.client.get('/'), 'data-auto="1"')  # mas continua atualizando

    def test_visualizador_nao_repoe(self):
        self.client.force_login(_usuario('ana', 'visualizador'))
        self.assertEqual(self.client.post(f'/impressoras/{self.imp.id}/repor/ciano/').status_code, 403)
        self.assertEqual(self.client.post('/reposicao/tudo/').status_code, 403)
        self.assertEqual(self._linha('ciano').na_sala, 0)

    def test_chave_invalida_da_404(self):
        self.assertEqual(self.client.post(f'/impressoras/{self.imp.id}/repor/roxo/').status_code, 404)


class TrocaComOrigemTests(NovasFuncoesBase):
    def test_troca_pegando_do_estoque_nao_mexe_na_reserva(self):
        self._definir(10, na_sala=1)
        self.client.post(f'/impressoras/{self.imp.id}/trocar/ciano/', {'origem': 'estoque'})
        self.nivel.refresh_from_db()
        self.toner.refresh_from_db()
        self.assertEqual((self.nivel.nivel, self.nivel.na_sala, self.toner.estoque_unidade), (100, 1, 4))
        self.assertEqual(Troca.objects.get().origem, 'estoque')

    def test_troca_do_estoque_funciona_mesmo_com_sala_sem_reserva(self):
        self._definir(10, na_sala=0)
        self.client.post(f'/impressoras/{self.imp.id}/trocar/ciano/', {'origem': 'estoque'})
        self.nivel.refresh_from_db()
        self.assertEqual((self.nivel.nivel, self.nivel.na_sala), (100, 0))

    def test_troca_do_estoque_sem_estoque_recusa(self):
        self.toner.estoque_unidade = 0
        self.toner.save()
        self._definir(10, na_sala=1)
        self.client.post(f'/impressoras/{self.imp.id}/trocar/ciano/', {'origem': 'estoque'})
        self.nivel.refresh_from_db()
        self.assertEqual(self.nivel.nivel, 10)
        self.assertEqual(Troca.objects.count(), 0)

    def test_origem_padrao_e_a_reserva_da_sala(self):
        self._definir(10, na_sala=2)
        self.client.post(f'/impressoras/{self.imp.id}/trocar/ciano/')
        self.nivel.refresh_from_db()
        self.assertEqual(self.nivel.na_sala, 1)
        self.assertEqual(Troca.objects.get().origem, 'sala')

    def test_cenario_troquei_e_deixei_reserva(self):
        """Admin pega 2 do estoque: 1 instala e 1 deixa na sala (que estava sem reserva)."""
        self._definir(10, na_sala=0)
        self.client.post(f'/impressoras/{self.imp.id}/trocar/ciano/', {'origem': 'estoque'})
        self.client.post(f'/impressoras/{self.imp.id}/repor/ciano/')
        self.nivel.refresh_from_db()
        self.toner.refresh_from_db()
        self.assertEqual((self.nivel.nivel, self.nivel.na_sala, self.toner.estoque_unidade), (100, 1, 3))


class AjusteDeContagemTests(NovasFuncoesBase):
    def _salvar(self, sala, residuo=0):
        return self.client.post(f'/impressoras/{self.imp.id}/atualizar/', {
            'nivel_ciano': 50, 'sala_ciano': sala, 'residuo_na_sala': residuo})

    def test_mudar_a_contagem_a_mao_fica_registrado(self):
        self._salvar(3)
        a = AjusteReserva.objects.get()
        self.assertEqual((a.descricao, a.anterior, a.novo, a.usuario_nome),
                         ('Toner Ciano (azul)', 0, 3, 'admin_teste'))

    def test_sem_mudanca_na_contagem_nao_registra(self):
        self._salvar(0)  # só o nível mudou
        self.assertEqual(AjusteReserva.objects.count(), 0)

    def test_ajuste_nao_mexe_no_estoque(self):
        self._salvar(3)
        self.toner.refresh_from_db()
        self.assertEqual(self.toner.estoque_unidade, 5)

    def test_historico_mostra_o_ajuste(self):
        self._salvar(3)
        self.assertContains(self.client.get('/historico/'), 'de <strong>0</strong> para <strong>3</strong>')
