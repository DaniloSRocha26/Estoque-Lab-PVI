from django.conf import settings
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

    @property
    def colorida(self):
        return self.toners.count() > 1

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
    nivel = models.PositiveIntegerField(default=100)
    na_sala = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['impressora', 'cor'], name='impressora_cor_unica')]
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
