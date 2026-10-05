# Colocar o sistema no ar (PythonAnywhere, plano gratuito)

O site fica em `https://SEU_USUARIO.pythonanywhere.com`, com HTTPS, e o banco (SQLite) fica guardado no próprio servidor.

**Antes de começar, saiba que:**
- A consulta é aberta: qualquer pessoa com o link vê estoque, impressoras, pedidos e histórico (com nomes de quem trocou e pediu). Só editar exige login.
- No plano gratuito, o site **para depois de 1 mês** se não for renovado (passo 9).
- No plano gratuito não há tarefas agendadas: o **backup é manual** (passo 10).
- O endereço é sempre `seu_usuario.pythonanywhere.com` e **não pode ser mudado** no plano gratuito (nem o nome de usuário). Escolha o nome da conta com calma, antes de criar o site.

> ### ⚠️ Troque os textos de exemplo antes de rodar qualquer comando
> Os textos em MAIÚSCULAS são **lugares reservados**: se você colar o comando sem trocá-los, ele roda **com o texto de exemplo**, e isso causa problemas reais.
>
> | Texto de exemplo | Troque por | Exemplo |
> |---|---|---|
> | `SEU_USUARIO` | seu nome de usuário do PythonAnywhere (ele vira o endereço do site) | `Danilo26` |
> | `SEU_LOGIN` | o login que **você** vai usar para editar o sistema | `danilo` |
> | `UMA_SENHA_FORTE` | uma senha **sua**, com 12 caracteres ou mais, sem o símbolo `!` | (crie a sua) |
> | `Seu Nome` | seu nome, que aparece no menu e no histórico | `Danilo` |
>
> Por que isso importa: este guia está num repositório **público**. Uma conta criada com `SEU_LOGIN` e `UMA_SENHA_FORTE` teria login e senha que qualquer pessoa conhece. E um `.env` com `SEU_USUARIO` faz o site mostrar "Bad Request (400)".

Nos comandos abaixo, troque `SEU_USUARIO` pelo seu nome de usuário do PythonAnywhere.

---

## 1. Criar a conta
Em <https://www.pythonanywhere.com>, crie uma conta **Beginner (gratuita)**. O nome de usuário vira o endereço do site.

## 2. Baixar o projeto
No painel, abra **Consoles → Bash** e rode:

```bash
git clone https://github.com/DaniloSRocha26/Estoque-Lab-PVI.git
cd Estoque-Lab-PVI
```

## 3. Criar o ambiente e instalar
```bash
mkvirtualenv --python=/usr/bin/python3.13 estoque
pip install -r requirements.txt
```

## 4. Configurar o servidor
Ainda no console, dentro de `Estoque-Lab-PVI`:

```bash
python manage.py preparar_producao --host SEU_USUARIO.pythonanywhere.com
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py criar_usuario SEU_LOGIN --perfil admin --senha "UMA_SENHA_FORTE" --nome "Seu Nome"
```

- `preparar_producao` cria o arquivo `.env` com uma **chave secreta nova** e o modo de produção ligado. Esse arquivo fica só no servidor e nunca vai para o GitHub.
- O banco começa **vazio**. Depois, cadastre os modelos, impressoras e itens em **Cadastros**.
- Crie aqui as contas dos administradores (uma por pessoa). Mantenha as **aspas** em volta da senha e evite o símbolo `!` nela (o terminal o interpreta de outro jeito).

**Confira antes de seguir** (no mesmo console, dentro de `Estoque-Lab-PVI`):

```bash
grep ALLOWED .env
python manage.py shell -c "from django.contrib.auth.models import User; print(list(User.objects.values_list('username', flat=True)))"
```

- O primeiro deve mostrar o **seu** endereço (`DJANGO_ALLOWED_HOSTS=seu_usuario.pythonanywhere.com`). Se mostrar `SEU_USUARIO`, corrija:
  ```bash
  rm .env
  python manage.py preparar_producao --host SEU_USUARIO.pythonanywhere.com
  ```
- O segundo deve listar **só o seu login**. Se aparecer `SEU_LOGIN` ou outro usuário de teste, crie o seu e apague o outro (crie antes de apagar, para nunca ficar sem administrador):
  ```bash
  python manage.py shell -c "from django.contrib.auth.models import User; print(User.objects.filter(username='SEU_LOGIN').delete())"
  ```
  Aqui `SEU_LOGIN` é o nome da conta **a apagar**.

## 5. Criar o site
Na aba **Web**, clique em **Add a new web app**:
1. Confirme o endereço `SEU_USUARIO.pythonanywhere.com`.
2. Escolha **Manual configuration** (não escolha a opção "Django").
3. Escolha **Python 3.13**.

## 6. Preencher a aba Web
Na mesma aba **Web**:

| Seção | Campo | Valor |
|---|---|---|
| **Code** | Source code | `/home/SEU_USUARIO/Estoque-Lab-PVI` |
| **Code** | Working directory | `/home/SEU_USUARIO/Estoque-Lab-PVI` |
| **Virtualenv** | (caminho) | `estoque` |
| **Static files** | URL / Directory | `/static/` → `/home/SEU_USUARIO/Estoque-Lab-PVI/staticfiles` |
| **Security** | Force HTTPS | **ligado** |

## 7. Arquivo WSGI
Na seção **Code**, clique no link do **WSGI configuration file**, **apague todo o conteúdo** e cole:

```python
import os
import sys

path = '/home/SEU_USUARIO/Estoque-Lab-PVI'
if path not in sys.path:
    sys.path.insert(0, path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

Salve.

## 8. Ligar
Clique no botão verde **Reload** no topo da aba **Web** e abra `https://SEU_USUARIO.pythonanywhere.com`.

Se aparecer erro, veja o **Error log**, no fim da aba **Web**.

**Problemas comuns**

| O que aparece | Causa provável | O que fazer |
|---|---|---|
| **Bad Request (400)** | O endereço no `.env` está errado (por exemplo `SEU_USUARIO`) | Refaça o `.env` como no passo 4 e clique em **Reload** |
| Página de erro do PythonAnywhere ("Something went wrong") | Erro no código ou na configuração | Abra o **Error log** e leia as últimas linhas |
| Site abre, mas sem cores e sem menu | Os arquivos de estilo não foram juntados, ou o campo **Static files** da aba Web está errado | Rode `python manage.py collectstatic --noinput`, confira o campo e clique em **Reload** |
| "Sem permissão" ou não consegue entrar | Login ou senha errados | Entre pelo console e crie o usuário de novo (passo 4) |

---

## 9. Todo mês: renovar
Na aba **Web**, clique no botão **"Run until 1 month from today"**. Sem isso, o site para depois de 1 mês. Vale pôr um lembrete no calendário.

## 10. Backup (sugestão: toda sexta)
No console Bash:

```bash
cd ~/Estoque-Lab-PVI && workon estoque
python manage.py backup_banco
```

Depois, na aba **Files**, entre em `Estoque-Lab-PVI/backups/` e **baixe** o arquivo mais recente para o seu computador. O comando guarda as 10 cópias mais recentes no servidor, mas o backup só está seguro quando também está fora dele.

**Para restaurar um backup:** envie o arquivo pela aba **Files** para a pasta `Estoque-Lab-PVI`, renomeie-o para `db.sqlite3` (substituindo o atual) e clique em **Reload** na aba **Web**.

## 11. Atualizar o site depois de mudanças no GitHub
```bash
cd ~/Estoque-Lab-PVI && workon estoque
python manage.py backup_banco
git pull
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
```

Depois, clique em **Reload** na aba **Web** e abra o site com `Ctrl+F5`, para o navegador não usar o visual antigo guardado. Se a atualização incluir arquivos de estilo ou JavaScript novos, o `collectstatic` é obrigatório.
