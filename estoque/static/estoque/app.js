(function () {
  'use strict';

  // Limites vindos do servidor (estoque/niveis.py), para ficarem sempre iguais aos das telas
  var NIVEL_BAIXO = parseInt(document.body.dataset.nivelBaixo, 10);
  var NIVEL_MEDIO = parseInt(document.body.dataset.nivelMedio, 10);
  var INTERVALO_AUTO = 60 * 1000;   // atualização automática: a cada 1 minuto
  var PAUSA_APOS_DIGITAR = 30 * 1000; // não atualiza se você mexeu em algum campo há menos que isso
  var filtros = { busca: '', baixos: false, aba: null };

  // ----- Tema claro/escuro -----
  document.getElementById('alternar-tema').addEventListener('click', function () {
    var atual = document.documentElement.getAttribute('data-bs-theme');
    var novo = atual === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-bs-theme', novo);
    try { localStorage.setItem('tema', novo); } catch (e) {}
  });

  // ----- Avisos (toasts) -----
  function toast(texto, tipo) {
    var classe = tipo === 'error' ? 'text-bg-danger' : 'text-bg-success';
    var el = document.createElement('div');
    el.className = 'toast align-items-center border-0 ' + classe;
    el.setAttribute('role', 'alert');
    el.innerHTML = '<div class="d-flex"><div class="toast-body"></div>' +
      '<button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button></div>';
    el.querySelector('.toast-body').textContent = texto;
    document.getElementById('toasts').appendChild(el);
    var t = new bootstrap.Toast(el, { delay: 6000 });
    el.addEventListener('hidden.bs.toast', function () { el.remove(); });
    t.show();
  }

  function mostrarMensagens(raiz) {
    raiz.querySelectorAll('[data-mensagem]').forEach(function (m) {
      toast(m.textContent.trim(), m.getAttribute('data-mensagem'));
      m.remove();
    });
  }

  // ----- Filtros do painel -----
  function aplicarFiltros() {
    var termo = filtros.busca.trim().toLowerCase();
    document.querySelectorAll('.tab-pane').forEach(function (aba) {
      var visiveis = 0;
      aba.querySelectorAll('.card-impressora').forEach(function (card) {
        var texto = card.getAttribute('data-busca') || '';
        var nivel = parseInt(card.getAttribute('data-nivel'), 10);
        var ok = (!termo || texto.indexOf(termo) !== -1) && (!filtros.baixos || nivel <= NIVEL_BAIXO);
        card.parentElement.classList.toggle('d-none', !ok);
        if (ok) visiveis++;
      });
      var vazio = aba.querySelector('.sem-resultado');
      if (vazio) vazio.classList.toggle('d-none', visiveis > 0);
    });
  }

  function restaurarAba() {
    if (!filtros.aba) return;
    var botao = document.querySelector('[data-aba="' + filtros.aba + '"]');
    if (botao) {
      // sem animação ao restaurar, para não "piscar" depois de salvar
      var painel = document.querySelector(botao.getAttribute('data-bs-target'));
      document.querySelectorAll('.nav-pills .nav-link.active, .tab-pane.active').forEach(function (el) {
        el.classList.remove('active', 'show');
      });
      botao.classList.add('active');
      painel.classList.add('active', 'show');
    }
  }

  function iniciarPagina() {
    var busca = document.getElementById('filtro-busca');
    var baixos = document.getElementById('filtro-baixos');
    if (busca) {
      busca.value = filtros.busca;
      busca.addEventListener('input', function () { filtros.busca = busca.value; aplicarFiltros(); });
    }
    if (baixos) {
      baixos.checked = filtros.baixos;
      baixos.addEventListener('change', function () { filtros.baixos = baixos.checked; aplicarFiltros(); });
    }
    restaurarAba();
    aplicarFiltros();
    mostrarMensagens(document);
  }

  // Guarda a aba escolhida para reabri-la depois de salvar
  document.addEventListener('shown.bs.tab', function (e) {
    filtros.aba = e.target.getAttribute('data-aba');
  });

  // Valor do controle deslizante de nível em tempo real
  document.addEventListener('input', function (e) {
    if (e.target.matches('[data-nivel-range]')) {
      var linha = e.target.closest('.linha-cor');
      var valor = parseInt(e.target.value, 10);
      linha.querySelector('[data-nivel-saida]').textContent = valor + '%';
      linha.querySelector('.progress-bar').style.width = valor + '%';
      linha.querySelector('.progress').setAttribute('aria-valuenow', valor);
      e.target.style.setProperty('--valor', valor + '%');  // pinta a parte já "preenchida" da trilha
      var estado = linha.querySelector('[data-nivel-estado]');
      var nivel = valor <= NIVEL_BAIXO ? ['Baixo', 'danger'] : valor <= NIVEL_MEDIO ? ['Médio', 'warning'] : ['Bom', 'success'];
      estado.textContent = nivel[0];
      estado.className = 'badge text-bg-' + nivel[1];
    }
  });

  // ----- Proteção contra perder o que está sendo digitado -----
  var ultimaInteracao = 0;
  ['input', 'change', 'keydown', 'pointerdown'].forEach(function (nome) {
    document.addEventListener(nome, function (e) {
      var conteudo = document.getElementById('conteudo');
      if (!conteudo.contains(e.target)) return;
      ultimaInteracao = Date.now();
      if (nome === 'input' || nome === 'change') {
        var form = e.target.closest ? e.target.closest('form[data-ajax]') : null;
        if (form) form.dataset.sujo = '1';  // tem alteração ainda não salva
      }
    }, true);
  });

  function editando() {
    var conteudo = document.getElementById('conteudo');
    if (conteudo.querySelector('form[data-sujo], form.salvando, .dropdown-menu.show')) return true;
    var ativo = document.activeElement;
    var campoDeTexto = ativo && conteudo.contains(ativo) &&
      ativo.matches('input:not([type=checkbox]):not([type=radio]), select, textarea');
    return !!campoDeTexto && (Date.now() - ultimaInteracao) < PAUSA_APOS_DIGITAR;
  }

  // ----- Atualização automática -----
  var ultimaAtualizacao = Date.now();

  function marcarHora() {
    ultimaAtualizacao = Date.now();
  }

  function atualizarSozinho() {
    var conteudo = document.getElementById('conteudo');
    if (!conteudo.dataset.auto || document.hidden || editando()) return;
    fetch(location.href, { credentials: 'same-origin', headers: { 'X-Requested-With': 'fetch' } })
      .then(function (resp) {
        if (!resp.ok || (resp.redirected && resp.url.indexOf('/entrar/') !== -1)) throw new Error('ignorar');
        return resp.text();
      }).then(function (html) {
        if (editando()) return; // a pessoa começou a editar enquanto a página carregava
        var novo = new DOMParser().parseFromString(html, 'text/html').getElementById('conteudo');
        if (!novo) return;
        mostrarMensagens(novo);
        conteudo.innerHTML = novo.innerHTML;
        iniciarPagina();
        marcarHora();
      }).catch(function () { /* sem conexão: tenta de novo no próximo ciclo */ });
  }

  if (document.getElementById('conteudo').dataset.auto) {
    marcarHora();
    setInterval(atualizarSozinho, INTERVALO_AUTO);
    document.addEventListener('visibilitychange', function () {
      if (!document.hidden && Date.now() - ultimaAtualizacao > INTERVALO_AUTO) atualizarSozinho();
    });
  }

  // ----- Envio de formulários sem recarregar -----
  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (!form.matches('form[data-ajax]')) return;
    e.preventDefault();
    if (form.classList.contains('salvando')) return; // ainda enviando: evita registrar duas vezes
    if (form.dataset.confirmar && !confirm(form.dataset.confirmar)) return;
    var cancelando = form.elements.status && form.elements.status.value === 'cancelado';
    if (form.dataset.confirmarCancelar && cancelando && !confirm(form.dataset.confirmarCancelar)) return;
    var trocandoModelo = form.elements.modelo && form.elements.modelo.value !== form.dataset.modeloAtual;
    if (form.dataset.confirmarModelo && trocandoModelo && !confirm(form.dataset.confirmarModelo)) return;
    form.classList.add('salvando');

    fetch(form.action, {
      method: 'POST',
      body: new FormData(form),
      headers: { 'X-Requested-With': 'fetch' },
      credentials: 'same-origin'
    }).then(function (resp) {
      if (resp.redirected && resp.url.indexOf('/entrar/') !== -1) {
        window.location.href = resp.url; // sessão expirou
        throw new Error('Sessão expirada.');
      }
      if (resp.status === 403) throw new Error('Sem permissão: seu perfil é somente consulta.');
      if (!resp.ok) throw new Error('Falha ao salvar (' + resp.status + ').');
      return resp.text();
    }).then(function (html) {
      var novo = new DOMParser().parseFromString(html, 'text/html').getElementById('conteudo');
      var atual = document.getElementById('conteudo');
      mostrarMensagens(novo);
      atual.innerHTML = novo.innerHTML;
      iniciarPagina();
      marcarHora();
    }).catch(function (erro) {
      form.classList.remove('salvando');
      toast(erro.message || 'Erro de conexão.', 'error');
    });
  });

  iniciarPagina();
})();
