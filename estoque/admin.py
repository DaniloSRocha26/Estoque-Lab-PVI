from django.contrib import admin

from .models import Consumivel, Impressora, ModeloImpressora, Pedido


@admin.register(Consumivel)
class ConsumivelAdmin(admin.ModelAdmin):
    list_display = ('nome', 'tipo', 'estoque_unidade', 'estoque_minimo')
    list_filter = ('tipo',)


@admin.register(ModeloImpressora)
class ModeloImpressoraAdmin(admin.ModelAdmin):
    list_display = ('nome', 'tipo', 'toner', 'caixa_residuo')


@admin.register(Impressora)
class ImpressoraAdmin(admin.ModelAdmin):
    list_display = ('nome', 'modelo', 'numero_serie', 'localizacao', 'nivel_toner')


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('consumivel', 'quantidade', 'status', 'solicitante', 'criado_em')
    list_filter = ('status',)
