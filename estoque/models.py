from django.conf import settings
from django.core.validators import MaxValueValidator
from django.db import models

# Ordem de exibição (padrão CMYK)
CORES = [
    ('preto', 'Preto'),
    ('ciano', 'Ciano (azul)'),
    ('magenta', 'Magenta'),
    ('amarelo', 'Amarelo'),
]
ORDEM_CORES = [valor for valor, _ in CORES]


class ComAtualizacao(models.Model):
    """Guarda quando o registro foi salvo pela última vez (inclusive em saves parciais)."""
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        campos = kwargs.get('update_fields')
        if campos is not None:
            kwargs['update_fields'] = {*campos, 'atualizado_em'}
        super().save(*args, **kwargs)


class Consumivel(ComAtualizacao):
    TIPOS = [('toner', 'Toner'), ('residuo', 'Caixa de resíduo')]
    nome = models.CharField(max_length=100)
    tipo = models.CharField(max_length=10, choices=TIPOS)
    estoque_unidade = models.PositiveIntegerField(default=0)
    estoque_minimo = models.PositiveIntegerField(default=1)

    def __str__(self):
        return self.nome


class ModeloImpressora(models.Model):
    """Ex.: Konica (4 toners: preto, ciano, magenta, amarelo) ou Epson (só preto)."""
    nome = models.CharField(max_length=100)
    tipo = models.CharField(max_length=50)  # ex: laser mono, laser colorida
    caixa_residuo = models.ForeignKey(Consumivel, on_delete=models.PROTECT,
                                      related_name='+', null=True, blank=True,
                                      limit_choices_to={'tipo': 'residuo'})

    def __str__(self):
        return self.nome

    def toners_ordenados(self):
        return sorted(self.toners.all(), key=lambda t: ORDEM_CORES.index(t.cor))


class ModeloToner(models.Model):
    """Qual toner do estoque o modelo usa em cada cor."""
    modelo = models.ForeignKey(ModeloImpressora, on_delete=models.CASCADE, related_name='toners')
    cor = models.CharField(max_length=10, choices=CORES)
    consumivel = models.ForeignKey(Consumivel, on_delete=models.PROTECT, related_name='+',
                                   limit_choices_to={'tipo': 'toner'})

    class Meta:
        constraints = [models.UniqueConstraint(fields=['modelo', 'cor'], name='modelo_cor_unica')]
        verbose_name = 'toner do modelo'
        verbose_name_plural = 'toners do modelo'

    def __str__(self):
        return f'{self.modelo} · {self.get_cor_display()} → {self.consumivel}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        for impressora in self.modelo.impressora_set.all():
            impressora.sincronizar_niveis()

    def delete(self, *args, **kwargs):
        modelo = self.modelo
        super().delete(*args, **kwargs)
        for impressora in modelo.impressora_set.all():
            impressora.sincronizar_niveis()


class Impressora(models.Model):
    nome = models.CharField(max_length=100)
    modelo = models.ForeignKey(ModeloImpressora, on_delete=models.PROTECT)
    numero_serie = models.CharField(max_length=100, unique=True)
    localizacao = models.CharField(max_length=150)
    residuo_na_sala = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        campos = kwargs.get('update_fields')
        if campos is None or 'modelo' in campos:  # só o modelo define quais cores existem
            self.sincronizar_niveis()

    def sincronizar_niveis(self):
        """Garante um NivelToner por cor do modelo (e remove cores que o modelo não usa)."""
        cores = {t.cor for t in self.modelo.toners.all()}
        self.niveis.exclude(cor__in=cores).delete()
        existentes = set(self.niveis.values_list('cor', flat=True))
        for cor in ORDEM_CORES:
            if cor in cores and cor not in existentes:
                NivelToner.objects.create(impressora=self, cor=cor)

    def niveis_ordenados(self):
        return sorted(self.niveis.all(), key=lambda n: ORDEM_CORES.index(n.cor))


class NivelToner(ComAtualizacao):
    """Nível (0 a 100, informado pelo usuário) e reserva na sala de uma cor da impressora."""
    impressora = models.ForeignKey(Impressora, on_delete=models.CASCADE, related_name='niveis')
    cor = models.CharField(max_length=10, choices=CORES)
    nivel = models.PositiveIntegerField(default=100, validators=[MaxValueValidator(100)])
    na_sala = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['impressora', 'cor'], name='impressora_cor_unica'),
            models.CheckConstraint(condition=models.Q(nivel__lte=100), name='nivel_ate_100'),
        ]
        verbose_name = 'nível de toner'
        verbose_name_plural = 'níveis de toner'

    def __str__(self):
        return f'{self.impressora} · {self.get_cor_display()}: {self.nivel}%'


class Troca(models.Model):
    """Histórico: cada vez que um toner foi trocado em uma impressora."""
    impressora = models.ForeignKey(Impressora, on_delete=models.SET_NULL, null=True,
                                   related_name='trocas')
    impressora_nome = models.CharField(max_length=100)  # mantém o histórico se a impressora sair
    cor = models.CharField(max_length=10, choices=CORES)
    toner = models.ForeignKey(Consumivel, on_delete=models.SET_NULL, null=True, related_name='+')
    toner_nome = models.CharField(max_length=100, blank=True)
    nivel_anterior = models.PositiveIntegerField()
    ORIGENS = [('sala', 'Reserva da sala'), ('estoque', 'Estoque da unidade')]
    origem = models.CharField(max_length=7, choices=ORIGENS, default='sala')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                null=True, blank=True, related_name='+')
    usuario_nome = models.CharField(max_length=150, blank=True)
    registrado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-registrado_em', '-id']
        verbose_name = 'troca de toner'
        verbose_name_plural = 'trocas de toner'

    def __str__(self):
        return f'{self.impressora_nome} · {self.get_cor_display()} · {self.registrado_em:%d/%m/%Y}'


class Reposicao(models.Model):
    """Histórico: toner ou caixa de resíduo que saiu do estoque da unidade para a reserva da sala."""
    impressora = models.ForeignKey(Impressora, on_delete=models.SET_NULL, null=True,
                                   related_name='reposicoes')
    impressora_nome = models.CharField(max_length=100)
    cor = models.CharField(max_length=10, choices=CORES, blank=True)  # vazio para caixa de resíduo
    item = models.ForeignKey(Consumivel, on_delete=models.SET_NULL, null=True, related_name='+')
    item_nome = models.CharField(max_length=100)
    quantidade = models.PositiveIntegerField()
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                null=True, blank=True, related_name='+')
    usuario_nome = models.CharField(max_length=150, blank=True)
    registrado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-registrado_em', '-id']
        verbose_name = 'reposição na sala'
        verbose_name_plural = 'reposições na sala'

    def __str__(self):
        return f'{self.quantidade}x {self.item_nome} → {self.impressora_nome}'


class AjusteReserva(models.Model):
    """Histórico: a contagem da reserva na sala foi corrigida à mão (sem mexer no estoque)."""
    impressora = models.ForeignKey(Impressora, on_delete=models.SET_NULL, null=True,
                                   related_name='ajustes')
    impressora_nome = models.CharField(max_length=100)
    descricao = models.CharField(max_length=100)  # ex.: "Toner Ciano" ou "Caixa de resíduo"
    cor = models.CharField(max_length=10, choices=CORES, blank=True)
    anterior = models.PositiveIntegerField()
    novo = models.PositiveIntegerField()
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                null=True, blank=True, related_name='+')
    usuario_nome = models.CharField(max_length=150, blank=True)
    registrado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-registrado_em', '-id']
        verbose_name = 'ajuste de contagem'
        verbose_name_plural = 'ajustes de contagem'

    def __str__(self):
        return f'{self.impressora_nome} · {self.descricao}: {self.anterior} → {self.novo}'


class AjusteEstoque(models.Model):
    """Histórico: a quantidade no estoque da unidade mudou fora de pedido, troca ou reposição."""
    item = models.ForeignKey(Consumivel, on_delete=models.SET_NULL, null=True, related_name='ajustes')
    item_nome = models.CharField(max_length=100)
    anterior = models.PositiveIntegerField()
    novo = models.PositiveIntegerField()
    motivo = models.CharField(max_length=200, blank=True)  # vazio = corrigido à mão
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                null=True, blank=True, related_name='+')
    usuario_nome = models.CharField(max_length=150, blank=True)
    registrado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-registrado_em', '-id']
        verbose_name = 'ajuste de estoque'
        verbose_name_plural = 'ajustes de estoque'

    def __str__(self):
        return f'{self.item_nome}: {self.anterior} → {self.novo}'


class Pedido(models.Model):
    STATUS = [('pendente', 'Pendente'), ('enviado', 'Enviado'), ('recebido', 'Recebido'),
              ('cancelado', 'Cancelado')]
    FINAIS = ('recebido', 'cancelado')  # depois destes o pedido não muda mais
    consumivel = models.ForeignKey(Consumivel, on_delete=models.PROTECT)
    quantidade = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=STATUS, default='pendente')
    solicitante = models.CharField(max_length=100)
    observacao = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    finalizado_em = models.DateTimeField(null=True, blank=True)  # quando foi recebido ou cancelado
    finalizado_por = models.CharField(max_length=150, blank=True)

    def __str__(self):
        return f'{self.quantidade}x {self.consumivel} ({self.status})'
