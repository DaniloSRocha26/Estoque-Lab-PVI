# Controle de Toner

Sistema web (Python + Django) para acompanhar o nível de toner das impressoras de uma unidade, o estoque de toners e caixas de resíduo, a reserva guardada em cada sala e os pedidos de reposição.

No ar em: <https://Danilo26.pythonanywhere.com>

## Onde está cada informação

| Arquivo | Para quê |
|---|---|
| **README.md** (este) | Rodar o projeto em outro computador, fazer alterações e mudar de servidor |
| [DEPLOY.md](DEPLOY.md) | Colocar o site no ar no PythonAnywhere e mantê-lo (renovar, backup, atualizar) |
| [Relatório.md](Relatório.md) | Situação do projeto, regras de negócio, o que falta e ideias |
| [project-1.md](project-1.md) | Planejamento original. As instruções de instalação dele são do início do projeto e estão **desatualizadas**: use este README |

---

## 1. Rodar no seu computador (desenvolvimento)

Precisa de **Python 3.12 ou mais novo** e do **Git**. (O projeto foi feito com Python 3.14 no computador e roda em 3.13 no servidor.)

```bash
git clone https://github.com/DaniloSRocha26/Estoque-Lab-PVI.git
cd Estoque-Lab-PVI
python -m venv venv
venv\Scripts\activate          # no Linux ou Mac: source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py criar_usuario SEU_LOGIN --perfil admin --senha "SUA_SENHA" --nome "Seu Nome"
python manage.py runserver
```

Abra <http://127.0.0.1:8000>. Para editar, clique em **Entrar para editar**, no menu lateral.

> **Troque os textos em MAIÚSCULAS** (`SEU_LOGIN`, `SUA_SENHA`, `Seu Nome`) pelos seus. Mantenha as aspas na senha e evite o símbolo `!` nela. Não rode o comando com os textos de exemplo.

Detalhes:
- O banco do seu computador (`db.sqlite3`) é **separado** do banco do site no ar. Nada que você cadastrar aqui aparece lá, e o contrário também.
- Para ter dados de teste (Konica e Epson fictícias): `python manage.py carregar_exemplo --limpar`. Atenção: o `--limpar` **apaga tudo** do banco local antes de carregar.
- O visual carrega Bootstrap e ícones pela internet (CDN): é preciso estar online.
- Para criar mais usuários, entre como admin e use **Cadastros → Usuários**.

## 2. Fazer alterações no sistema

1. **Edite** os arquivos no computador.
2. **Teste:** `python manage.py test` (todos devem passar) e abra o site para ver como ficou.
3. Se você mudou os **modelos** (`estoque/models.py`), gere a migração e inclua o arquivo gerado no commit:
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```
4. **Envie para o GitHub:**
   ```bash
   git add -A
   git commit -m "Descreva o que mudou"
   git push origin main
   ```
5. **Atualize o site no ar:** siga o [passo 11 do DEPLOY.md](DEPLOY.md) (backup, `git pull`, `migrate`, `collectstatic` e **Reload**). Depois, abra o site com `Ctrl+F5`.

Onde mexer nas regras mais comuns:
- Limites de **Baixo** (25%) e **Médio** (55%), reserva ideal e dias para "desatualizada": `estoque/niveis.py`.
- Telas: `estoque/templates/estoque/`. Visual: `estoque/static/estoque/app.css` e `tema.css`. Comportamento no navegador: `estoque/static/estoque/app.js`.
- Regras de estoque, reposição, troca e pedidos: `estoque/services.py`.

## 3. O que NÃO está no GitHub

Estes itens ficam só no computador ou no servidor. **Guarde cópias** deles:

| Item | O que é | Se perder |
|---|---|---|
| `db.sqlite3` | Todos os dados do sistema (impressoras, estoque, pedidos, histórico **e as contas de usuário**) | É a única cópia. Por isso o **backup toda sexta** (DEPLOY.md, passo 10) e baixar o arquivo para fora do servidor |
| `.env` (só no servidor) | Chave secreta e endereço do site | Pode ser recriado com `preparar_producao`. A consequência é só desconectar quem estava logado |
| `backups/`, `staticfiles/`, `venv/` | Cópias do banco, arquivos de estilo reunidos e ambiente Python | Se recriam com os comandos do guia |

## 4. Mudar de servidor ou de conta (refazer o deploy)

1. Siga o [DEPLOY.md](DEPLOY.md) **do passo 1 ao 8**, na conta ou servidor novo. O endereço do site muda: use o novo no `preparar_producao --host ...`.
2. Para **levar os dados** do site antigo:
   - No site antigo, rode `python manage.py backup_banco` e baixe o arquivo mais recente da pasta `backups/` (aba **Files**).
   - No site novo, **antes do primeiro Reload**, envie esse arquivo para a pasta do projeto e renomeie-o para `db.sqlite3` (substituindo o que existir), como no passo 10 do DEPLOY.md.
   - As **contas de usuário vêm junto** com o banco. Se preferir começar do zero, pule este passo e crie o admin pelo passo 4 do DEPLOY.md.
3. No plano gratuito do PythonAnywhere, o endereço é sempre `usuario.pythonanywhere.com` e **não pode ser mudado**: para ter outro endereço é preciso criar uma conta nova (ou assinar um plano pago).

## 5. Testes

```bash
python manage.py test
```

Os testes cobrem as regras (alertas, reposição, troca, pedidos), as permissões de acesso e as páginas. O JavaScript (atualização automática, controle deslizante, menus) **não** tem teste automático: confira no navegador depois de mexer nele.

## 6. Estrutura do projeto

```
config/            configurações do Django (settings.py lê o .env em produção)
estoque/
  models.py        dados: itens, modelos, impressoras, níveis, pedidos e históricos
  services.py      regras: alertas, reposição, troca, pedidos
  niveis.py        limites (Baixo, Médio, reserva ideal)
  views.py         telas de consulta e edição
  cadastros.py     telas de Cadastros
  usuarios.py      gestão de usuários e perfis
  acesso.py        regra de quem pode editar
  templates/       páginas HTML
  static/          CSS e JavaScript
  management/      comandos: criar_usuario, preparar_producao, backup_banco, carregar_exemplo
  migrations/      histórico das mudanças no banco
```
