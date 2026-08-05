from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('tasks/', views.task_list, name='task_list'),
    path('tasks/create/', views.task_create, name='task_create'),
    path('tasks/<int:pk>/edit/', views.task_update, name='task_update'),
    path('tasks/<int:pk>/delete/', views.task_delete, name='task_delete'),
    path('tasks/<int:pk>/toggle/', views.task_toggle, name='task_toggle'),
    path('tasks/<int:pk>/archive/', views.task_archive, name='task_archive'),
    path('tasks/archived/', views.archived_tasks, name='archived_tasks'),

    path('tasks/<int:task_pk>/subtask/create/', views.subtask_create, name='subtask_create'),
    path('subtasks/<int:pk>/toggle/', views.subtask_toggle, name='subtask_toggle'),
    path('subtasks/<int:pk>/delete/', views.subtask_delete, name='subtask_delete'),

    path('categories/', views.category_list, name='category_list'),
    path('categories/create/', views.category_create, name='category_create'),
    path('categories/<int:pk>/delete/', views.category_delete, name='category_delete'),

    path('analytics/', views.analytics, name='analytics'),

    path('signup/', views.signup, name='signup'),
]
