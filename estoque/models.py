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
