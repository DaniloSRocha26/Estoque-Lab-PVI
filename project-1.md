# Controle de Toner

Sistema web para monitorar o nível de toner das impressoras de uma unidade, o estoque de toners e caixas de resíduo, e registrar pedidos de reposição.

## Objetivo

Substituir o controle manual por uma página onde qualquer pessoa consegue ver, em segundos, quais impressoras estão com pouco toner, se há reposição disponível na sala ou no estoque da unidade, e se já existe pedido em andamento.

## Requisitos

Cada impressora mostra:
- Nome, tipo e número de série
- Localização na unidade
- Barra com o nível atual de toner (informado manualmente pelo usuário)
- Quantidade de toners e caixas de resíduo disponíveis na sala, para troca

A unidade mostra:
- Quantidade de toners e caixas de resíduo no estoque da unidade

Regra de negócio: um modelo de impressora sempre usa o mesmo toner (e a mesma caixa de resíduo).

### Alerta de reposição

Para cada toner (e caixa de resíduo), o sistema compara o estoque da unidade com o estoque mínimo desejado e verifica se alguma impressora que usa esse item está sem reserva na sala. Se o estoque está baixo e há impressora sem reserva, aparece um aviso como "Necessário pedir 3 unidades do toner X".

- Quantidade sugerida: estoque mínimo menos estoque atual (mínimo de 1)
- Se já existir pedido pendente ou enviado para aquele item, o aviso mostra "pedido em andamento" em vez de repetir o alerta

### Pedidos

- Registro interno de pedidos de toner ou caixa de resíduo, com quantidade, status e observação
- Status: pendente, enviado, recebido
- O alerta tem um botão "Criar pedido" já preenchido com a quantidade sugerida
- Ao marcar como "recebido", a quantidade soma automaticamente no estoque da unidade
- No MVP não há envio para ninguém (e-mail, sede ou fornecedor). Isso fica para uma fase futura

## Perfis de acesso (fase 2)

- **Admin** (2 pessoas): edita nível de toner, estoques, pedidos e cadastros.
- **Visualizador** (pessoal da sede): somente consulta.

No MVP não haverá login. A divisão de perfis entra depois.

## Stack

- Python + Django
- SQLite no desenvolvimento, PostgreSQL em produção
- Hospedagem: Render, Railway ou PythonAnywhere (decidir na fase de deploy)
- Editor: VS Code

Motivos: login, grupos de permissão e painel admin já vêm no Django, o banco é modelado em SQL de verdade e o histórico futuro permite análise com Pandas.

## Modelo de dados

- **Consumivel**: nome, tipo (toner ou caixa de resíduo), estoque_unidade, estoque_minimo
- **ModeloImpressora**: nome, tipo, toner (FK), caixa_residuo (FK, opcional)
- **Impressora**: nome, modelo (FK), numero_serie (único), localizacao, nivel_toner (0 a 100), toner_na_sala, residuo_na_sala
- **Pedido**: consumivel (FK), quantidade, status, solicitante (nome digitado, sem login), observacao, criado_em

## Roadmap

**Fase 1: MVP sem login**
1. Criar projeto e tabelas (instruções abaixo)
2. Registrar os modelos no painel admin do Django para cadastrar dados
3. Página principal com um card por impressora e barra de nível
4. Bloco com o estoque da unidade
5. Forma simples de atualizar o nível de toner e as quantidades
6. Alerta de reposição (estoque baixo + impressora sem reserva)
7. Pedidos: criar a partir do alerta, mudar status e somar ao estoque ao receber

**Fase 2: Perfis**
- Login, grupo "admin" e grupo "visualizador"
- Esconder e bloquear edição para visualizadores

**Fase 3: Deploy**
- Configurar PostgreSQL, variáveis de ambiente e hospedagem

**Fase 4: Melhorias**
- Alerta visual quando o nível da impressora ficar abaixo de um limite
- Histórico de trocas de toner e consumo por impressora
- Previsão de quando o toner acaba
- Envio de pedido por e-mail para a sede ou fornecedor

## Setup (passo 1)

No terminal do VS Code:

```
mkdir controle-toner
cd controle-toner
python -m venv venv
venv\Scripts\activate
pip install django
django-admin startproject config .
python manage.py startapp estoque
```

No Linux ou Mac, ativar com `source venv/bin/activate`.

Em `config/settings.py`, adicionar `'estoque'` em `INSTALLED_APPS` e ajustar:

```python
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Bahia'
```

## Models (estoque/models.py)

```python
from django.db import models


class Consumivel(models.Model):
    TIPOS = [('toner', 'Toner'), ('residuo', 'Caixa de resíduo')]
    nome = models.CharField(max_length=100)
    tipo = models.CharField(max_length=10, choices=TIPOS)
    estoque_unidade = models.PositiveIntegerField(default=0)
    estoque_minimo = models.PositiveIntegerField(default=1)

    def __str__(self):
        return self.nome


class ModeloImpressora(models.Model):
    nome = models.CharField(max_length=100)
    tipo = models.CharField(max_length=50)  # ex: laser mono, laser colorida
    toner = models.ForeignKey(Consumivel, on_delete=models.PROTECT,
                              related_name='+', limit_choices_to={'tipo': 'toner'})
    caixa_residuo = models.ForeignKey(Consumivel, on_delete=models.PROTECT,
                                      related_name='+', null=True, blank=True,
                                      limit_choices_to={'tipo': 'residuo'})

    def __str__(self):
        return self.nome


class Impressora(models.Model):
    nome = models.CharField(max_length=100)
    modelo = models.ForeignKey(ModeloImpressora, on_delete=models.PROTECT)
    numero_serie = models.CharField(max_length=100, unique=True)
    localizacao = models.CharField(max_length=150)
    nivel_toner = models.PositiveIntegerField(default=100)  # 0 a 100, informado pelo usuário
    toner_na_sala = models.PositiveIntegerField(default=0)
    residuo_na_sala = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.nome


class Pedido(models.Model):
    STATUS = [('pendente', 'Pendente'), ('enviado', 'Enviado'), ('recebido', 'Recebido')]
    consumivel = models.ForeignKey(Consumivel, on_delete=models.PROTECT)
    quantidade = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=STATUS, default='pendente')
    solicitante = models.CharField(max_length=100)
    observacao = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.quantidade}x {self.consumivel} ({self.status})'
```

Depois:

```
python manage.py makemigrations
python manage.py migrate
```

Se você já rodou as migrações antes de adicionar `estoque_minimo` e `Pedido`, rode os dois comandos de novo.

## Próximo passo

Registrar os modelos em `estoque/admin.py`, criar um superusuário (`python manage.py createsuperuser`) e cadastrar algumas impressoras reais para testar. Em seguida, montar a página principal com as barras de nível, depois o alerta e os pedidos.

## Pendências

- Levantar a lista real de impressoras, modelos e toners da unidade
- Definir o limite de nível que será considerado baixo
- Definir o estoque mínimo de cada toner e caixa de resíduo
- Escolher a plataforma de hospedagem
