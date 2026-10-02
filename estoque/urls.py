from django.urls import path

from . import views

urlpatterns = [
    path('', views.painel, name='painel'),
    path('impressoras/<int:pk>/atualizar/', views.atualizar_impressora, name='atualizar_impressora'),
    path('consumiveis/<int:pk>/atualizar/', views.atualizar_consumivel, name='atualizar_consumivel'),
    path('pedidos/', views.pedidos, name='pedidos'),
    path('pedidos/criar/', views.criar_pedido, name='criar_pedido'),
    path('pedidos/<int:pk>/status/', views.status_pedido, name='status_pedido'),
]
