# Relatório do projeto: Controle de Toner

Situação do projeto, regras de negócio adotadas, o que falta e ideias para o futuro.
O planejamento original está em [project-1.md](project-1.md).

Última atualização deste relatório: 03/10/2026.

---

## 1. Resumo

Sistema web (Python + Django) para acompanhar o nível de toner das impressoras de uma unidade, o estoque de toners e caixas de resíduo, a reserva guardada em cada sala e os pedidos de reposição.

- **Fase 1 (MVP): concluída.**
- **Fase 2 (perfis de acesso): concluída**, com uma decisão diferente do planejado (ver seção 4).
- **Fase 3 (deploy): não iniciada.**
- **Fase 4 (melhorias): parcialmente feita** (histórico de trocas e "atualizado em" já existem; faltam previsão de consumo e e-mail).

O sistema ainda **não está no ar**: roda apenas no computador de desenvolvimento, com SQLite.

---

## 2. O que já está pronto

### Páginas
| Página | Endereço | Quem acessa | Conteúdo |
|---|---|---|---|
| Estoque | `/` | todos | Aviso geral, estoque da unidade (com bolinha da cor do toner), **Salas para reabastecer**, **O que pedir** |
| Impressoras | `/impressoras/` | todos | Cards por impressora, com abas **Todas** e uma por modelo (ex.: Konica, Epson), busca e filtro "Só toner baixo" |
| Pedidos | `/pedidos/` | todos | Lista de pedidos; admin cria e muda o status |
| Histórico | `/historico/` | todos | Abas: Trocas de toner, Reposições na sala, Ajustes de contagem |
| Cadastros | `/cadastros/` | só admin | Impressoras, modelos, itens de estoque e usuários |

### Funcionalidades
- **Toner por cor:** a Konica tem 4 toners (preto, ciano, magenta, amarelo) e a Epson só o preto. Cada cor tem nível, reserva na sala e toner próprio no estoque.
- **Cadastro simplificado:** ao criar um modelo, o sistema cria sozinho os toners de cada cor e a caixa de resíduo. Ao criar uma impressora, os níveis por cor aparecem automaticamente.
- **Alerta "O que pedir":** aparece sempre que o item está abaixo do mínimo ("Pouco"), mesmo com as salas abastecidas, e também quando o estoque não dá para repor as salas sem reserva. A quantidade sugerida cobre a reposição das salas **e** ainda deixa o mínimo no estoque: `mínimo + falta nas salas − estoque − já pedido` (no mínimo 1). Se os pedidos pendentes ou enviados já cobrem isso, mostra "pedido já feito"; se não cobrem, sugere pedir o resto.
- **Pedidos:** pendente, enviado, recebido ou cancelado. Ao marcar como recebido, a quantidade soma no estoque (uma única vez). Recebido e cancelado são finais e guardam quando e quem finalizou.
- **Troquei o toner:** em cada cor, com duas origens: *usei a reserva da sala* ou *peguei do estoque*. O nível volta a 100% e a troca vai para o histórico.
- **Repor na sala / Salas para reabastecer:** passa do estoque para a reserva da sala o que falta para chegar à reserva ideal. Há botão por linha e **Repor tudo** (repõe o que o estoque alcança e deixa o resto na lista).
- **Contagem manual da reserva:** continua editável no card; cada mudança fica registrada em "Ajustes de contagem" (de X para Y) e **não** mexe no estoque.
- **Correção manual do estoque:** fica registrada em "Ajustes de estoque" (na página Estoque e em Cadastros).
- **Trocar o modelo de uma impressora** (Cadastros): pede confirmação. Em cada cor e na caixa de resíduo, se o modelo novo usa o mesmo item, a reserva continua; se usa outro, a reserva da sala **volta para o estoque** do item antigo (registrado em "Ajustes de contagem" e "Ajustes de estoque") e a cor recomeça com nível 100% e reserva 0.
- **Duas pessoas editando ao mesmo tempo:** o card só grava os números que a pessoa mudou. Se outra pessoa mudou o **mesmo** número nesse meio-tempo, o sistema recusa e pede para conferir, em vez de apagar a mudança do outro.
- **"Atualizado há…":** em cada impressora e item de estoque. Impressora sem conferência há mais de 7 dias aparece em vermelho ("confira os níveis").
- **Atualização automática:** a página recarrega os dados a cada minuto, mas **não atualiza** se houver campo alterado e não salvo, se a pessoa estiver digitando há menos de 30 segundos, se um menu estiver aberto ou se a aba estiver em segundo plano.
- **Visual:** Bootstrap, letras e botões grandes, estado sempre escrito em palavras (Baixo, Médio, Bom), tema claro por padrão com botão para o escuro, edição sem recarregar a página.

---

## 3. Regras de negócio adotadas

### Os três "números" do sistema
| O quê | Onde fica | Como muda |
|---|---|---|
| **Nível do toner instalado** (0 a 100%) | por impressora e cor | informado pelo admin (controle deslizante) ou volta a 100% ao registrar uma troca |
| **Reserva na sala** | por impressora e cor (e caixa de resíduo) | sobe com **Repor**; desce ao trocar usando a reserva; pode ser corrigida à mão |
| **Estoque da unidade** | por item | desce com **Repor** e com a troca "peguei do estoque"; sobe quando um pedido é marcado como recebido |

### Valores definidos
| Regra | Valor | Onde mudar |
|---|---|---|
| Nível **Baixo** | até 25% | `estoque/niveis.py` |
| Nível **Médio** | até 55% (acima disso, **Bom**) | `estoque/niveis.py` |
| Reserva ideal por sala | 1 de cada cor e 1 caixa de resíduo | `estoque/niveis.py` |
| Impressora "desatualizada" | mais de 7 dias sem conferência | `estoque/niveis.py` |
| Estoque mínimo | definido item a item (padrão ao criar um modelo: 2) | Cadastros, aba Itens de estoque |

### Rotina de sexta-feira (fluxo previsto)
1. Abrir **Estoque** e ir em **Salas para reabastecer** (o aviso amarelo do topo leva direto).
2. Clicar em **Repor tudo**. O que faltar no estoque continua na lista e, se o estoque estiver abaixo do mínimo, aparece em **O que pedir**.

---

## 4. Perfis de acesso (Fase 2)

- **Sem login:** qualquer pessoa **consulta** estoque, impressoras, pedidos e histórico (somente leitura). Há o botão **Entrar para editar**.
- **Admin:** edita tudo e acessa Cadastros (inclusive a gestão de usuários).
- **Visualizador:** perfil com login e somente leitura. Como a consulta é aberta, hoje ele quase não tem uso; foi mantido caso se queira contas individuais.
- As alterações são **bloqueadas no servidor**, e não só escondidas na tela.
- O sistema não deixa remover ou desativar o último administrador ativo, nem excluir o próprio usuário.

> **Diferença em relação ao planejado:** o `project-1.md` previa login para todos. Foi decidido deixar a **consulta aberta**, e o login só para editar.

### Criar o primeiro administrador
```
venv\Scripts\activate
python manage.py criar_usuario NOME --perfil admin --senha SENHA --nome "Nome Completo"
python manage.py runserver
```

---

## 5. O que ainda falta

### 5.1 Deploy (Fase 3)
- [ ] Escolher a hospedagem (sugestão: **Render**; alternativas: Railway ou PythonAnywhere).
- [ ] Trocar o SQLite por **PostgreSQL** em produção.
- [x] Ler a configuração de **variáveis de ambiente**: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0`, `DJANGO_ALLOWED_HOSTS` (separados por vírgula). Sem elas, roda em modo de desenvolvimento.
- [ ] **Gerar uma `DJANGO_SECRET_KEY` nova** para produção: a chave de desenvolvimento está no histórico do git.
- [ ] Banco de dados por variável de ambiente (PostgreSQL).
- [ ] Limitar tentativas de login (por exemplo `django-axes`): com a consulta aberta, a senha é a única barreira.
- [ ] Servir arquivos estáticos em produção (por exemplo WhiteNoise) e usar um servidor de aplicação (por exemplo gunicorn).
- [ ] Ativar HTTPS e os cookies seguros (`SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`).
- [ ] Definir **backup** do banco. O `db.sqlite3` não vai para o GitHub (está no `.gitignore`).
- [x] Decidido (03/10/2026): o banco de produção **começa vazio**.

### 5.2 Dados reais
- [ ] Cadastrar as impressoras reais, os modelos, os toners e as caixas de resíduo.
- [ ] Definir o **estoque mínimo** de cada item.
- [ ] Criar as contas dos administradores (a previsão é de 2 pessoas).

### 5.3 Decisões pendentes
- [ ] **Adiado (03/10/2026): o perfil "Operador" não será feito por enquanto.** Descrição original: para quem troca o toner no sábado sem acesso ao estoque: só registraria a troca, sem editar estoque nem cadastros. Alternativa: essas pessoas só avisam e o admin registra depois. Sem isso, o sistema fica desatualizado até o registro.
- [ ] Manter ou remover o perfil **Visualizador**, já que a consulta é aberta.
- [ ] Tornar os **limites configuráveis pela tela** (hoje 25%, 55% e reserva 1 ficam no código).

### 5.4 Verificações recomendadas
- [x] **Interface conferida no navegador (computador, tema claro e escuro)** em 03/10/2026, com prints e cliques automáticos no Edge. Os 105 testes automáticos cobrem o servidor; o JavaScript foi conferido no navegador.
- **Celular: decidido não adaptar por enquanto** (03/10/2026). No celular, o menu do topo sai da largura da tela.
- [ ] A interface carrega Bootstrap e ícones por **CDN**: precisa de internet. Se a unidade tiver rede restrita, trazer esses arquivos para dentro do projeto.

---

> **Descartadas em 03/10/2026:** previsão de quando o toner acaba, botão "Pedir tudo", exportar/automatizar o pedido no Office Total (os pedidos são feitos lá, todos de uma vez) e lista para imprimir na sexta.

## 6. Ideias para o futuro (Fase 4 e além)

| Ideia | Observação |
|---|---|
| **Pedido por e-mail** para a sede ou fornecedor | O botão "Criar pedido" já gera os dados; falta o envio |
| **Previsão de quando o toner acaba** | Usa o histórico de trocas e o consumo por impressora |
| **Consumo por impressora** (gráficos) | O histórico de trocas já guarda os dados de base |
| **Exportar ou imprimir** pedidos e histórico (PDF ou planilha) | |
| **Lista para imprimir na sexta** (Salas para reabastecer) | Conferência física no papel |
| **Aviso automático** (e-mail) de impressora com nível baixo ou sala sem reserva | |
| **Preenchimento do controle deslizante na cor do toner** | Hoje é azul para todas as cores |
| **Unir barra e controle deslizante** em um só elemento | Deixaria o card ainda menor |
| **Observação por troca** (ex.: "papel enroscou") | |
| **Registro de fotos ou etiquetas** das impressoras | Só se for útil na prática |

---

## 7. Informações técnicas

- **Stack:** Python 3.14, Django 6.1, SQLite (desenvolvimento), Bootstrap 5 e JavaScript puro.
- **Testes:** `python manage.py test` (105 testes).
- **Estrutura principal**
  - `estoque/models.py`: dados (Consumivel, ModeloImpressora, ModeloToner, Impressora, NivelToner, Pedido, Troca, Reposicao, AjusteReserva, AjusteEstoque)
  - `estoque/services.py`: regras (alertas, reposição, troca, pedidos)
  - `estoque/niveis.py`: limites e reserva ideal
  - `estoque/acesso.py` e `estoque/usuarios.py`: perfis e gestão de usuários
  - `estoque/views.py` e `estoque/cadastros.py`: telas
  - `estoque/templates/` e `estoque/static/`: visual e JavaScript
- **Dados de exemplo (apenas desenvolvimento):** `python manage.py carregar_exemplo --limpar` (apaga tudo antes de carregar).
- **Migrações:** 8 (a `0002` converte dados antigos de toner único para toner por cor).
- **Admin do Django (`/admin/`):** o histórico é somente leitura, e estoque, reservas e status de pedido não podem ser editados por lá (essas mudanças passam pelas telas, que registram tudo).
