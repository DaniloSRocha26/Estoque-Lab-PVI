from django.contrib import admin

from .models import (AjusteEstoque, AjusteReserva, Consumivel, Impressora, ModeloImpressora,
                     ModeloToner, NivelToner, Pedido, Reposicao, Troca)


class SoLeituraNaEdicao:
    """Campos que só podem mudar pelas telas do sistema, que registram a mudança no histórico.

    No admin eles ficam livres ao criar o registro e bloqueados ao editar."""
    campos_bloqueados = ()

    def get_readonly_fields(self, request, obj=None):
        return (*super().get_readonly_fields(request, obj), *(self.campos_bloqueados if obj else ()))


class HistoricoAdmin(admin.ModelAdmin):
    """Histórico é registro de auditoria: só consulta."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Consumivel)
class ConsumivelAdmin(SoLeituraNaEdicao, admin.ModelAdmin):
    list_display = ('nome', 'tipo', 'estoque_unidade', 'estoque_minimo')
    list_filter = ('tipo',)
    campos_bloqueados = ('estoque_unidade',)


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
    readonly_fields = ('cor', 'na_sala')  # a reserva muda pela tela, que registra o ajuste

    def has_add_permission(self, request, obj=None):
        return False  # os níveis são criados automaticamente conforme as cores do modelo


@admin.register(Impressora)
class ImpressoraAdmin(SoLeituraNaEdicao, admin.ModelAdmin):
    list_display = ('nome', 'modelo', 'numero_serie', 'localizacao')
    inlines = [NivelTonerInline]
    # o modelo muda por Cadastros, que devolve ao estoque a reserva que não serve mais
    campos_bloqueados = ('modelo', 'residuo_na_sala')


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('consumivel', 'quantidade', 'status', 'solicitante', 'criado_em')
    list_filter = ('status',)
    # mudar o status por aqui não somaria o recebido no estoque: use a página Pedidos
    readonly_fields = ('status', 'finalizado_em', 'finalizado_por')


@admin.register(Troca)
class TrocaAdmin(HistoricoAdmin):
    list_display = ('registrado_em', 'impressora_nome', 'cor', 'toner_nome', 'nivel_anterior', 'usuario_nome')
    list_filter = ('cor',)


@admin.register(Reposicao)
class ReposicaoAdmin(HistoricoAdmin):
    list_display = ('registrado_em', 'impressora_nome', 'item_nome', 'quantidade', 'usuario_nome')


@admin.register(AjusteReserva)
class AjusteReservaAdmin(HistoricoAdmin):
    list_display = ('registrado_em', 'impressora_nome', 'descricao', 'anterior', 'novo', 'usuario_nome')


@admin.register(AjusteEstoque)
class AjusteEstoqueAdmin(HistoricoAdmin):
    list_display = ('registrado_em', 'item_nome', 'anterior', 'novo', 'motivo', 'usuario_nome')
