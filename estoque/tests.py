from django.contrib.auth.models import Group, User
from django.test import TestCase as DjangoTestCase

from .models import Consumivel, Impressora, ModeloImpressora, ModeloToner, Pedido
from .services import calcular_alertas, mudar_status_pedido


class TestCase(DjangoTestCase):
    """Os testes de funcionalidade rodam logados como admin."""

    def setUp(self):
        super().setUp()
        self.admin = _usuario('admin_teste', 'admin')
        self.client.force_login(self.admin)


def _usuario(nome, perfil, **extra):
    user = User.objects.create_user(nome, password='SenhaForte#2026', **extra)
    user.groups.add(Group.objects.get(name=perfil))
    return user


def _toner(nome, estoque=0, minimo=3):
    return Consumivel.objects.create(nome=nome, tipo='toner',
                                     estoque_unidade=estoque, estoque_minimo=minimo)


class AlertaETests(TestCase):
    def setUp(self):
        super().setUp()
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
        r = self.client.post('/pedidos/criar/', {**dados, 'voltar': 'estoque'})
        self.assertRedirects(r, '/')
        r = self.client.post('/pedidos/criar/', {**dados, 'voltar': 'impressoras'})
        self.assertRedirects(r, '/impressoras/')
        r = self.client.post('/pedidos/criar/', {**dados, 'voltar': 'http://externo.com'})
        self.assertRedirects(r, '/pedidos/')

    def test_paginas_respondem(self):
        for url in ('/', '/impressoras/', '/pedidos/'):
            self.assertEqual(self.client.get(url).status_code, 200)


class CoresTests(TestCase):
    def setUp(self):
        super().setUp()
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


class AbasTests(TestCase):
    def test_painel_cria_uma_aba_por_modelo(self):
        for nome, cor in (('Konica', 'ciano'), ('Epson', 'preto')):
            modelo = ModeloImpressora.objects.create(nome=nome, tipo='laser')
            ModeloToner.objects.create(modelo=modelo, cor=cor, consumivel=_toner(f'{nome} toner'))
            Impressora.objects.create(nome=f'{nome} 1', modelo=modelo,
                                      numero_serie=nome, localizacao='Sala')
        r = self.client.get('/impressoras/')
        self.assertEqual([g['modelo'].nome for g in r.context['grupos']], ['Epson', 'Konica'])
        self.assertContains(r, 'data-aba=', count=3)  # Todos + 2 modelos
        self.assertContains(r, 'card-impressora h-100', count=4)  # cada impressora em Todos e na sua aba


class CadastrosTests(TestCase):
    def _criar_modelo(self, nome='Konica', tipo='colorida', residuo='on'):
        dados = {'nome': nome, 'tipo': tipo, 'estoque_minimo': 2}
        if residuo:
            dados['usa_residuo'] = residuo
        return self.client.post('/cadastros/modelos/criar/', dados)

    def test_paginas_respondem(self):
        self.assertEqual(self.client.get('/cadastros/').status_code, 200)

    def test_modelo_colorido_cria_quatro_toners_e_residuo(self):
        self._criar_modelo()
        modelo = ModeloImpressora.objects.get(nome='Konica')
        self.assertEqual(sorted(t.cor for t in modelo.toners.all()),
                         ['amarelo', 'ciano', 'magenta', 'preto'])
        self.assertIsNotNone(modelo.caixa_residuo)
        self.assertEqual(Consumivel.objects.filter(tipo='toner').count(), 4)

    def test_modelo_mono_cria_so_preto_sem_residuo(self):
        self._criar_modelo('Epson', 'mono', residuo=None)
        modelo = ModeloImpressora.objects.get(nome='Epson')
        self.assertEqual([t.cor for t in modelo.toners.all()], ['preto'])
        self.assertIsNone(modelo.caixa_residuo)

    def test_impressora_nova_ganha_niveis_por_cor(self):
        self._criar_modelo()
        modelo = ModeloImpressora.objects.get(nome='Konica')
        self.client.post('/cadastros/impressoras/criar/', {
            'nome': 'K1', 'modelo': modelo.id, 'numero_serie': 'S1', 'localizacao': 'Lab'})
        self.assertEqual(Impressora.objects.get(nome='K1').niveis.count(), 4)

    def test_numero_de_serie_repetido_e_recusado(self):
        self._criar_modelo()
        modelo = ModeloImpressora.objects.get(nome='Konica')
        dados = {'nome': 'K1', 'modelo': modelo.id, 'numero_serie': 'S1', 'localizacao': 'Lab'}
        self.client.post('/cadastros/impressoras/criar/', dados)
        self.client.post('/cadastros/impressoras/criar/', {**dados, 'nome': 'K2'})
        self.assertEqual(Impressora.objects.count(), 1)

    def test_trocar_modelo_da_impressora_refaz_os_niveis(self):
        self._criar_modelo()
        self._criar_modelo('Epson', 'mono', residuo=None)
        konica = ModeloImpressora.objects.get(nome='Konica')
        epson = ModeloImpressora.objects.get(nome='Epson')
        imp = Impressora.objects.create(nome='X', modelo=konica, numero_serie='S9', localizacao='L')
        self.client.post(f'/cadastros/impressoras/{imp.id}/editar/', {
            'nome': 'X', 'modelo': epson.id, 'numero_serie': 'S9', 'localizacao': 'L'})
        self.assertEqual([n.cor for n in imp.niveis.all()], ['preto'])

    def test_nao_exclui_modelo_com_impressora(self):
        self._criar_modelo()
        modelo = ModeloImpressora.objects.get(nome='Konica')
        Impressora.objects.create(nome='X', modelo=modelo, numero_serie='S9', localizacao='L')
        self.client.post(f'/cadastros/modelos/{modelo.id}/excluir/')
        self.assertTrue(ModeloImpressora.objects.filter(pk=modelo.pk).exists())

    def test_nao_exclui_item_em_uso_mas_exclui_impressora(self):
        self._criar_modelo()
        modelo = ModeloImpressora.objects.get(nome='Konica')
        item = modelo.toners.first().consumivel
        self.client.post(f'/cadastros/itens/{item.id}/excluir/')
        self.assertTrue(Consumivel.objects.filter(pk=item.pk).exists())
        imp = Impressora.objects.create(nome='X', modelo=modelo, numero_serie='S9', localizacao='L')
        self.client.post(f'/cadastros/impressoras/{imp.id}/excluir/')
        self.assertFalse(Impressora.objects.filter(pk=imp.pk).exists())


class AcessoTests(DjangoTestCase):
    def setUp(self):
        self.toner = _toner('Toner X')
        self.visualizador = _usuario('ana', 'visualizador')
        self.admin = _usuario('chefe', 'admin')

    def test_anonimo_consulta_sem_controles(self):
        for url in ('/', '/impressoras/', '/pedidos/'):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            self.assertNotContains(r, 'data-ajax')
            self.assertContains(r, 'Entrar para editar')

    def test_anonimo_nao_acessa_cadastros(self):
        r = self.client.get('/cadastros/')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/entrar/', r['Location'])

    def test_anonimo_nao_altera_nada(self):
        r = self.client.post(f'/consumiveis/{self.toner.id}/atualizar/', {'estoque_unidade': 99})
        self.assertEqual(r.status_code, 302)
        self.toner.refresh_from_db()
        self.assertEqual(self.toner.estoque_unidade, 0)

    def test_visualizador_consulta_mas_nao_ve_controles(self):
        self.client.force_login(self.visualizador)
        for url in ('/', '/impressoras/', '/pedidos/'):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            self.assertNotContains(r, 'data-ajax')
        self.assertNotContains(self.client.get('/'), 'href="/cadastros/"')

    def test_visualizador_e_bloqueado_no_servidor(self):
        self.client.force_login(self.visualizador)
        self.assertEqual(self.client.get('/cadastros/').status_code, 403)
        r = self.client.post(f'/consumiveis/{self.toner.id}/atualizar/', {'estoque_unidade': 99})
        self.assertEqual(r.status_code, 403)
        r = self.client.post('/pedidos/criar/', {'consumivel': self.toner.id, 'quantidade': 1,
                                                  'solicitante': 'x'})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(Pedido.objects.count(), 0)
        r = self.client.post('/cadastros/modelos/criar/', {'nome': 'X', 'tipo': 'mono',
                                                           'estoque_minimo': 1})
        self.assertEqual(r.status_code, 403)
        self.toner.refresh_from_db()
        self.assertEqual(self.toner.estoque_unidade, 0)

    def test_admin_ve_controles_e_altera(self):
        self.client.force_login(self.admin)
        self.assertContains(self.client.get('/pedidos/'), 'data-ajax')
        self.client.post(f'/consumiveis/{self.toner.id}/atualizar/', {'estoque_unidade': 7})
        self.toner.refresh_from_db()
        self.assertEqual(self.toner.estoque_unidade, 7)

    def test_login_volta_para_a_pagina_de_origem(self):
        r = self.client.post('/entrar/?next=/pedidos/', {'username': 'chefe', 'password': 'SenhaForte#2026'})
        self.assertRedirects(r, '/pedidos/')

    def test_login_e_logout(self):
        r = self.client.post('/entrar/', {'username': 'ana', 'password': 'SenhaForte#2026'})
        self.assertRedirects(r, '/')
        self.client.post('/sair/')
        self.assertEqual(self.client.get('/cadastros/').status_code, 302)

    def test_senha_errada_nao_entra(self):
        r = self.client.post('/entrar/', {'username': 'ana', 'password': 'errada'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Usuário ou senha incorretos')


class UsuariosTests(TestCase):
    def test_admin_cria_usuario_visualizador(self):
        self.client.post('/cadastros/usuarios/criar/', {
            'username': 'joao', 'nome': 'João', 'senha': 'SenhaForte#2026', 'perfil': 'visualizador'})
        joao = User.objects.get(username='joao')
        self.assertEqual(list(joao.groups.values_list('name', flat=True)), ['visualizador'])
        self.assertTrue(joao.check_password('SenhaForte#2026'))

    def test_senha_fraca_e_recusada(self):
        self.client.post('/cadastros/usuarios/criar/', {
            'username': 'joao', 'senha': '123', 'perfil': 'visualizador'})
        self.assertFalse(User.objects.filter(username='joao').exists())

    def test_nao_remove_o_ultimo_admin(self):
        self.client.post(f'/cadastros/usuarios/{self.admin.id}/editar/', {
            'perfil': 'visualizador', 'ativo': 'on'})
        self.assertTrue(User.objects.get(pk=self.admin.pk).groups.filter(name='admin').exists())
        self.client.post(f'/cadastros/usuarios/{self.admin.id}/excluir/')
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())

    def test_promover_e_trocar_senha(self):
        ana = _usuario('ana', 'visualizador')
        self.client.post(f'/cadastros/usuarios/{ana.id}/editar/', {
            'perfil': 'admin', 'ativo': 'on', 'nova_senha': 'OutraSenha#2026'})
        ana.refresh_from_db()
        self.assertTrue(ana.groups.filter(name='admin').exists())
        self.assertFalse(ana.groups.filter(name='visualizador').exists())
        self.assertTrue(ana.check_password('OutraSenha#2026'))

    def test_pagina_de_cadastros_mostra_usuarios(self):
        self.assertContains(self.client.get('/cadastros/'), 'admin_teste')


class DivisaoDePaginasTests(TestCase):
    def setUp(self):
        super().setUp()
        self.toner = _toner('Toner X')
        modelo = ModeloImpressora.objects.create(nome='Epson', tipo='laser mono')
        ModeloToner.objects.create(modelo=modelo, cor='preto', consumivel=self.toner)
        Impressora.objects.create(nome='Epson Sala 2', modelo=modelo, numero_serie='E1',
                                  localizacao='Sala 2')

    def test_estoque_mostra_itens_e_nao_impressoras(self):
        r = self.client.get('/')
        self.assertContains(r, 'Estoque da unidade')
        self.assertContains(r, 'Toner X')
        self.assertNotContains(r, 'card-impressora')

    def test_impressoras_mostra_cards_e_nao_o_estoque(self):
        r = self.client.get('/impressoras/')
        self.assertContains(r, 'Epson Sala 2')
        self.assertNotContains(r, 'Estoque da unidade')

    def test_aviso_geral_aparece_nas_duas(self):
        for url in ('/', '/impressoras/'):
            self.assertContains(self.client.get(url), 'resumo-geral')

    def test_salvar_volta_para_a_pagina_certa(self):
        imp = Impressora.objects.get()
        r = self.client.post(f'/impressoras/{imp.id}/atualizar/', {
            'nivel_preto': 50, 'sala_preto': 1, 'residuo_na_sala': 0})
        self.assertRedirects(r, '/impressoras/')
        r = self.client.post(f'/consumiveis/{self.toner.id}/atualizar/', {'estoque_unidade': 4})
        self.assertRedirects(r, '/')
