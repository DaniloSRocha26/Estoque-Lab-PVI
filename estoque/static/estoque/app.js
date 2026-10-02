(function () {
  'use strict';

  var filtros = { busca: '', baixos: false };

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
    var t = new bootstrap.Toast(el, { delay: 3500 });
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
    var visiveis = 0;
    document.querySelectorAll('.card-impressora').forEach(function (card) {
      var texto = card.getAttribute('data-busca') || '';
      var nivel = parseInt(card.getAttribute('data-nivel'), 10);
      var ok = (!termo || texto.indexOf(termo) !== -1) && (!filtros.baixos || nivel <= 15);
      card.parentElement.classList.toggle('d-none', !ok);
      if (ok) visiveis++;
    });
    var vazio = document.getElementById('sem-resultado');
    if (vazio) vazio.classList.toggle('d-none', visiveis > 0 || !document.querySelector('.card-impressora'));
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
    aplicarFiltros();
    mostrarMensagens(document);
  }

  // Valor do controle deslizante de nível em tempo real
  document.addEventListener('input', function (e) {
    if (e.target.matches('[data-nivel-range]')) {
      var saida = e.target.closest('.linha-cor').querySelector('[data-nivel-saida]');
      if (saida) saida.textContent = e.target.value + '%';
    }
  });

  // ----- Envio de formulários sem recarregar -----
  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (!form.matches('form[data-ajax]')) return;
    e.preventDefault();
    form.classList.add('salvando');

    fetch(form.action, {
      method: 'POST',
      body: new FormData(form),
      headers: { 'X-Requested-With': 'fetch' },
      credentials: 'same-origin'
    }).then(function (resp) {
      if (!resp.ok) throw new Error('Falha ao salvar (' + resp.status + ').');
      return resp.text();
    }).then(function (html) {
      var novo = new DOMParser().parseFromString(html, 'text/html').getElementById('conteudo');
      var atual = document.getElementById('conteudo');
      mostrarMensagens(novo);
      atual.innerHTML = novo.innerHTML;
      iniciarPagina();
    }).catch(function (erro) {
      form.classList.remove('salvando');
      toast(erro.message || 'Erro de conexão.', 'error');
    });
  });

  iniciarPagina();
})();
