from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count, Q, Avg, F
from django.db.models.functions import TruncDate
from datetime import timedelta, datetime
import json

from .models import Task, SubTask, Category, Reminder, DailyAnalytics
from .forms import TaskForm, SubTaskForm, CategoryForm, ReminderForm, SignUpForm
from .ai_utils import parse_natural_language_task, generate_subtasks


def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Welcome to TaskFlow! Your account has been created.")
            return redirect('dashboard')
    else:
        form = SignUpForm()
    return render(request, 'registration/signup.html', {'form': form})


@login_required
def dashboard(request):
    user = request.user
    now = timezone.now()
    today = now.date()

    
    total = Task.objects.filter(user=user).count()
    pending = Task.objects.filter(user=user, status='pending').count()
    completed = Task.objects.filter(user=user, status='completed').count()
    in_progress = Task.objects.filter(user=user, status='in_progress').count()
    overdue = Task.objects.filter(user=user, status__in=['pending', 'in_progress']).filter(due_date__lt=now).count()
    completion_rate = round((completed / total * 100), 1) if total > 0 else 0

    # Recent tasks 
    recent_tasks = Task.objects.filter(user=user).select_related('category')[:8]

    # Urgent tasks
    urgent_tasks = Task.objects.filter(
        user=user, 
        priority='urgent',
        status__in=['pending', 'in_progress']
    ).order_by('due_date')[:5]

    # Tasks due the same day 
    today_tasks = Task.objects.filter(
        user=user,
        status__in=['pending', 'in_progress'],
        due_date__date=today
    )

    # Category distribution
    category_stats = Category.objects.filter(user=user).annotate(
        task_count=Count('tasks')
    ).values('name', 'color', 'task_count')

    # Weekly analytics
    week_start = today - timedelta(days=6)
    weekly_data = DailyAnalytics.objects.filter(
        user=user, 
        date__gte=week_start
    ).order_by('date')

    # Priority breakdown
    priority_breakdown = Task.objects.filter(user=user).values('priority').annotate(
        count=Count('id')
    ).order_by('priority')

    # Productivity streak
    streak = 0
    check_date = today
    while True:
        analytics = DailyAnalytics.objects.filter(user=user, date=check_date).first()
        if analytics and analytics.tasks_completed > 0:
            streak += 1
            check_date -= timedelta(days=1)
        else:
            break

    context = {
        'stats': {
            'total': total,
            'pending': pending,
            'completed': completed,
            'in_progress': in_progress,
            'overdue': overdue,
            'completion_rate': completion_rate,
        },
        'recent_tasks': recent_tasks,
        'urgent_tasks': urgent_tasks,
        'today_tasks': today_tasks,
        'category_stats': list(category_stats),
        'weekly_data': weekly_data,
        'priority_breakdown': list(priority_breakdown),
        'streak': streak,
    }
    return render(request, 'tasks/dashboard.html', context)


@login_required
def task_list(request):
    user = request.user
    status_filter = request.GET.get('status', '')
    priority_filter = request.GET.get('priority', '')
    category_filter = request.GET.get('category', '')
    search_query = request.GET.get('q', '')
    sort_by = request.GET.get('sort', '-created_at')

    tasks = Task.objects.filter(user=user).select_related('category').prefetch_related('subtasks')

    if status_filter:
        tasks = tasks.filter(status=status_filter)
    if priority_filter:
        tasks = tasks.filter(priority=priority_filter)
    if category_filter:
        tasks = tasks.filter(category_id=category_filter)
    if search_query:
        tasks = tasks.filter(Q(title__icontains=search_query) | Q(description__icontains=search_query))

    tasks = tasks.order_by(sort_by)

    categories = Category.objects.filter(user=user)

    context = {
        'tasks': tasks,
        'categories': categories,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'category_filter': category_filter,
        'search_query': search_query,
        'sort_by': sort_by,
        'status_choices': Task.STATUS_CHOICES,
        'priority_choices': Task.PRIORITY_CHOICES,
    }
    return render(request, 'tasks/task_list.html', context)


@login_required
def task_create(request):
    if request.method == 'POST':
        # Check for natural language input
        nl_input = request.POST.get('natural_language', '').strip()
        if nl_input:
            parsed = parse_natural_language_task(nl_input)
            
            # Convert due_date string to datetime object for the form
            due_date = None
            if parsed.get('due_date'):
                try:
                    from django.utils.dateparse import parse_datetime
                    due_date = parse_datetime(parsed['due_date'])
                except:
                    pass
            
            initial = {
                'title': parsed.get('title', nl_input),
                'priority': parsed.get('priority', 'medium'),
            }
            if due_date:
                # Format for datetime-local input
                initial['due_date'] = due_date.strftime('%Y-%m-%dT%H:%M')
            
            form = TaskForm(initial=initial, user=request.user)
            
            # Auto-suggest subtasks if it's a complex task
            subtask_suggestions = generate_subtasks(initial['title'])
            
            return render(request, 'tasks/task_form.html', {
                'form': form,
                'natural_language': nl_input,
                'subtask_suggestions': subtask_suggestions,
                'action': 'Create'
            })
        
        # Normal form submission
        form = TaskForm(request.POST, user=request.user)
        if form.is_valid():
            task = form.save(commit=False)
            task.user = request.user
            task.save()
            
            # Create any subtasks from suggestions
            subtasks_json = request.POST.get('subtasks_json', '[]')
            try:
                subtask_titles = json.loads(subtasks_json)
                for title in subtask_titles:
                    SubTask.objects.create(task=task, title=title)
            except:
                pass
            
            messages.success(request, "Task created with AI!")
            return redirect('task_list')
    else:
        form = TaskForm(user=request.user)
    
    return render(request, 'tasks/task_form.html', {
        'form': form, 
        'action': 'Create',
        'subtask_suggestions': []
    })

    if request.method == 'POST':
        form = TaskForm(request.POST, user=request.user)
        if form.is_valid():
            task = form.save(commit=False)
            task.user = request.user
            task.save()

            # Create reminder if set
            if task.reminder_at:
                Reminder.objects.create(task=task, remind_at=task.reminder_at)

            messages.success(request, "Task created successfully!")
            return redirect('task_list')
    else:
        form = TaskForm(user=request.user)

    categories = Category.objects.filter(user=request.user)
    return render(request, 'tasks/task_form.html', {'form': form, 'categories': categories, 'action': 'Create'})


@login_required
def task_update(request, pk):
    task = get_object_or_404(Task, pk=pk, user=request.user)
    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task, user=request.user)
        if form.is_valid():
            task = form.save()

            # Update reminder
            if task.reminder_at:
                Reminder.objects.filter(task=task).delete()
                Reminder.objects.create(task=task, remind_at=task.reminder_at)
            else:
                Reminder.objects.filter(task=task).delete()

            messages.success(request, "Task updated successfully!")
            return redirect('task_list')
    else:
        form = TaskForm(instance=task, user=request.user)

    categories = Category.objects.filter(user=request.user)
    subtasks = task.subtasks.all()
    return render(request, 'tasks/task_form.html', {
        'form': form, 
        'categories': categories, 
        'task': task,
        'subtasks': subtasks,
        'action': 'Edit'
    })


@login_required
def task_delete(request, pk):
    task = get_object_or_404(Task, pk=pk, user=request.user)
    if request.method == 'POST':
        task.delete()
        messages.success(request, "Task deleted successfully!")
        return redirect('task_list')
    return render(request, 'tasks/task_confirm_delete.html', {'task': task})


@login_required
def task_toggle(request, pk):
    task = get_object_or_404(Task, pk=pk, user=request.user)
    if request.method == 'POST':
        if task.status == 'completed':
            task.status = 'pending'
            task.completed_at = None
        else:
            task.status = 'completed'
            task.completed_at = timezone.now()
        task.save()

        # Update analytics
        update_daily_analytics(request.user)

        return JsonResponse({
            'status': task.status,
            'completed_at': task.completed_at.isoformat() if task.completed_at else None
        })
    return JsonResponse({'error': 'Invalid request'}, status=400)


@login_required
def task_archive(request, pk):
    task = get_object_or_404(Task, pk=pk, user=request.user)
    if request.method == 'POST':
        task.status = 'archived'
        task.save()
        messages.success(request, "Task archived.")
        return redirect('task_list')
    return render(request, 'tasks/task_confirm_archive.html', {'task': task})


@login_required
def archived_tasks(request):
    tasks = Task.objects.filter(user=request.user, status='archived').order_by('-updated_at')
    return render(request, 'tasks/archived_list.html', {'tasks': tasks})


@login_required
def subtask_create(request, task_pk):
    task = get_object_or_404(Task, pk=task_pk, user=request.user)
    if request.method == 'POST':
        form = SubTaskForm(request.POST)
        if form.is_valid():
            subtask = form.save(commit=False)
            subtask.task = task
            subtask.save()
            return JsonResponse({'id': subtask.id, 'title': subtask.title})
    return JsonResponse({'error': 'Invalid request'}, status=400)


@login_required
def subtask_toggle(request, pk):
    subtask = get_object_or_404(SubTask, pk=pk, task__user=request.user)
    if request.method == 'POST':
        subtask.is_completed = not subtask.is_completed
        subtask.save()

        # Check if all subtasks completed
        task = subtask.task
        all_done = all(s.is_completed for s in task.subtasks.all())
        if all_done and task.subtasks.exists():
            task.status = 'completed'
            task.completed_at = timezone.now()
            task.save()

        return JsonResponse({'is_completed': subtask.is_completed, 'all_done': all_done})
    return JsonResponse({'error': 'Invalid request'}, status=400)


@login_required
def subtask_delete(request, pk):
    subtask = get_object_or_404(SubTask, pk=pk, task__user=request.user)
    if request.method == 'POST':
        subtask.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'Invalid request'}, status=400)


@login_required
def category_list(request):
    categories = Category.objects.filter(user=request.user).annotate(
        task_count=Count('tasks')
    )
    return render(request, 'tasks/category_list.html', {'categories': categories})


@login_required
def category_create(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save(commit=False)
            category.user = request.user
            category.save()
            messages.success(request, "Category created!")
            return redirect('category_list')
    else:
        form = CategoryForm()
    return render(request, 'tasks/category_form.html', {'form': form, 'action': 'Create'})


@login_required
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk, user=request.user)
    if request.method == 'POST':
        category.delete()
        messages.success(request, "Category deleted.")
        return redirect('category_list')
    return render(request, 'tasks/category_confirm_delete.html', {'category': category})


@login_required
def analytics(request):
    user = request.user
    today = timezone.now().date()

    # Overall stats
    total_tasks = Task.objects.filter(user=user).count()
    completed_tasks = Task.objects.filter(user=user, status='completed').count()
    pending_tasks = Task.objects.filter(user=user, status='pending').count()

    # Monthly completion
    month_start = today.replace(day=1)
    monthly_completed = Task.objects.filter(
        user=user, 
        status='completed',
        completed_at__date__gte=month_start
    ).count()

    # Average completion time
    avg_time = Task.objects.filter(
        user=user, 
        status='completed',
        completed_at__isnull=False
    ).annotate(
        duration=F('completed_at') - F('created_at')
    ).aggregate(avg=Avg('duration'))['avg']

    # Priority distribution
    priority_data = list(Task.objects.filter(user=user).values('priority').annotate(
        count=Count('id')
    ).order_by('priority'))

    # Weekly trend
    week_data = []
    for i in range(6, -1, -1):
        date = today - timedelta(days=i)
        analytics_day = DailyAnalytics.objects.filter(user=user, date=date).first()
        week_data.append({
            'date': date.strftime('%a'),
            'created': analytics_day.tasks_created if analytics_day else 0,
            'completed': analytics_day.tasks_completed if analytics_day else 0,
        })

    # Category breakdown
    category_data = list(Category.objects.filter(user=user).annotate(
        count=Count('tasks')
    ).values('name', 'color', 'count'))

    context = {
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'pending_tasks': pending_tasks,
        'monthly_completed': monthly_completed,
        'avg_time': avg_time,
        'priority_data': priority_data,
        'week_data': week_data,
        'category_data': category_data,
    }
    return render(request, 'tasks/analytics.html', context)


def update_daily_analytics(user):
    """Update or create daily analytics record."""
    today = timezone.now().date()
    analytics, created = DailyAnalytics.objects.get_or_create(
        user=user,
        date=today,
        defaults={
            'tasks_created': Task.objects.filter(user=user, created_at__date=today).count(),
            'tasks_completed': Task.objects.filter(user=user, completed_at__date=today).count(),
            'tasks_overdue': Task.objects.filter(user=user, due_date__date__lt=today, status__in=['pending', 'in_progress']).count(),
        }
    )
    if not created:
        analytics.tasks_created = Task.objects.filter(user=user, created_at__date=today).count()
        analytics.tasks_completed = Task.objects.filter(user=user, completed_at__date=today).count()
        analytics.tasks_overdue = Task.objects.filter(user=user, due_date__date__lt=today, status__in=['pending', 'in_progress']).count()

    total_today = analytics.tasks_created
    analytics.completion_rate = round((analytics.tasks_completed / total_today * 100), 1) if total_today > 0 else 0
    analytics.save()
