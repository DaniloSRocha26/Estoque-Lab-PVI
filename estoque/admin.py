from django.contrib import admin

from .models import Consumivel, Impressora, ModeloImpressora, ModeloToner, NivelToner, Pedido, Troca


@admin.register(Consumivel)
class ConsumivelAdmin(admin.ModelAdmin):
    list_display = ('nome', 'tipo', 'estoque_unidade', 'estoque_minimo')
    list_filter = ('tipo',)


class ModeloTonerInline(admin.TabularInline):
    model = ModeloToner
    extra = 1
    max_num = 4


@admin.register(ModeloImpressora)
class ModeloImpressoraAdmin(admin.ModelAdmin):
    list_display = ('nome', 'tipo', 'cores', 'caixa_residuo')
    inlines = [ModeloTonerInline]

    @admin.display(description='Cores')
    def cores(self, obj):
        return ', '.join(t.get_cor_display() for t in obj.toners_ordenados())


class NivelTonerInline(admin.TabularInline):
    model = NivelToner
    extra = 0
    can_delete = False
    fields = ('cor', 'nivel', 'na_sala')
    readonly_fields = ('cor',)

    def has_add_permission(self, request, obj=None):
        return False  # os níveis são criados automaticamente conforme as cores do modelo


@admin.register(Impressora)
class ImpressoraAdmin(admin.ModelAdmin):
    list_display = ('nome', 'modelo', 'numero_serie', 'localizacao')
    inlines = [NivelTonerInline]


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('consumivel', 'quantidade', 'status', 'solicitante', 'criado_em')
    list_filter = ('status',)


@admin.register(Troca)
class TrocaAdmin(admin.ModelAdmin):
    list_display = ('registrado_em', 'impressora_nome', 'cor', 'toner_nome', 'nivel_anterior', 'usuario_nome')
    list_filter = ('cor',)
