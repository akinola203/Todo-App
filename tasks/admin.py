from django.contrib import admin
from .models import Task, SubTask, Category, Reminder, DailyAnalytics

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'priority', 'status', 'due_date', 'is_overdue', 'is_pinned']
    list_filter = ['priority', 'status', 'created_at']
    search_fields = ['title', 'description']
    date_hierarchy = 'created_at'

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'color']
    list_filter = ['user']

@admin.register(SubTask)
class SubTaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'task', 'is_completed']

@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = ['task', 'remind_at', 'is_sent']
    list_filter = ['is_sent']

@admin.register(DailyAnalytics)
class DailyAnalyticsAdmin(admin.ModelAdmin):
    list_display = ['user', 'date', 'tasks_created', 'tasks_completed', 'completion_rate']
    date_hierarchy = 'date'
