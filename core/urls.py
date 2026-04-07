from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('transacoes/', views.transaction_list, name='list'),
    path('transacoes/nova/', views.transaction_new, name='transaction_new'),
    path('transacoes/<int:pk>/editar/', views.transaction_edit, name='transaction_edit'),
    path('transacoes/<int:pk>/deletar/', views.transaction_delete, name='transaction_delete'),
    path('analise/', views.analysis, name='analysis'),
    path('categorias/', views.categories, name='categories'),
    path('categorias/<int:pk>/deletar/', views.category_delete, name='category_delete'),
    path('insights/', views.insights, name='insights'),
    path('perfil/', views.profile, name='profile'),
]
