from django.urls import path

from . import cadastros, usuarios, views

urlpatterns = [
    path('', views.pagina_estoque, name='estoque'),
    path('impressoras/', views.pagina_impressoras, name='impressoras'),
    path('impressoras/<int:pk>/trocar/<str:cor>/', views.trocar_toner_view, name='trocar_toner'),
    path('impressoras/<int:pk>/repor/<str:chave>/', views.repor_na_sala_view, name='repor_na_sala'),
    path('reposicao/tudo/', views.repor_tudo_view, name='repor_tudo'),
    path('historico/', views.pagina_historico, name='historico'),
    path('impressoras/<int:pk>/atualizar/', views.atualizar_impressora, name='atualizar_impressora'),
    path('consumiveis/<int:pk>/atualizar/', views.atualizar_consumivel, name='atualizar_consumivel'),
    path('pedidos/', views.pedidos, name='pedidos'),
    path('pedidos/criar/', views.criar_pedido, name='criar_pedido'),
    path('pedidos/<int:pk>/status/', views.status_pedido, name='status_pedido'),

    path('cadastros/', cadastros.cadastros, name='cadastros'),
    path('cadastros/impressoras/criar/', cadastros.impressora_criar, name='impressora_criar'),
    path('cadastros/impressoras/<int:pk>/editar/', cadastros.impressora_editar, name='impressora_editar'),
    path('cadastros/impressoras/<int:pk>/excluir/', cadastros.impressora_excluir, name='impressora_excluir'),
    path('cadastros/modelos/criar/', cadastros.modelo_criar, name='modelo_criar'),
    path('cadastros/modelos/<int:pk>/renomear/', cadastros.modelo_renomear, name='modelo_renomear'),
    path('cadastros/modelos/<int:pk>/excluir/', cadastros.modelo_excluir, name='modelo_excluir'),
    path('cadastros/itens/criar/', cadastros.consumivel_criar, name='consumivel_criar'),
    path('cadastros/itens/<int:pk>/editar/', cadastros.consumivel_editar, name='consumivel_editar'),
    path('cadastros/itens/<int:pk>/excluir/', cadastros.consumivel_excluir, name='consumivel_excluir'),
    path('cadastros/usuarios/criar/', usuarios.usuario_criar, name='usuario_criar'),
    path('cadastros/usuarios/<int:pk>/editar/', usuarios.usuario_editar, name='usuario_editar'),
    path('cadastros/usuarios/<int:pk>/excluir/', usuarios.usuario_excluir, name='usuario_excluir'),
]
