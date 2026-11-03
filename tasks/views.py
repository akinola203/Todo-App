import json
import logging
from datetime import timedelta, datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.utils import timezone
from django.db.models import Count, Q, Avg, F
from django.conf import settings
from django.views.decorators.http import require_POST

from .models import Task, SubTask, Category, Reminder, DailyAnalytics, PushSubscription
from .forms import TaskForm, SubTaskForm, CategoryForm, ReminderForm, SignUpForm
from .ai_utils import (
    parse_natural_language_task, 
    generate_subtasks,
    get_ai_greeting, 
    get_procrastination_alert, 
    get_smart_schedule_tip,
    get_xp_and_level
)

logger = logging.getLogger(__name__)


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

    total = Task.objects.filter(user=user).count()
    pending = Task.objects.filter(user=user, status='pending').count()
    completed = Task.objects.filter(user=user, status='completed').count()
    overdue = Task.objects.filter(
        user=user, 
        status__in=['pending', 'in_progress'],
        due_date__lt=now
    ).count()
    completion_rate = round((completed / total * 100), 1) if total > 0 else 0

    recent_tasks = (
        Task.objects.filter(user=user)
        .select_related('category')
        .prefetch_related('subtasks')[:8]
    )
    urgent_tasks = (
        Task.objects.filter(user=user, priority='urgent', status__in=['pending', 'in_progress'])
        .select_related('category')
        .order_by('due_date')[:5]
    )

    ai_greeting = get_ai_greeting(user)
    procrastination_alert = get_procrastination_alert(user)
    schedule_tip = get_smart_schedule_tip(user)
    gamification = get_xp_and_level(user)

    context = {
        'stats': {
            'total': total,
            'pending': pending,
            'completed': completed,
            'overdue': overdue,
            'completion_rate': completion_rate
        },
        'recent_tasks': recent_tasks,
        'urgent_tasks': urgent_tasks,
        'ai_greeting': ai_greeting,
        'procrastination_alert': procrastination_alert,
        'schedule_tip': schedule_tip,
        'gamification': gamification,
    }
    return render(request, 'tasks/dashboard.html', context)


@login_required
def task_list(request):
    user = request.user
    status_filter = request.GET.get('status', '')
    priority_filter = request.GET.get('priority', '')
    category_filter = request.GET.get('category', '')
    search_query = request.GET.get('q', '').strip()
    sort_by = request.GET.get('sort', '-created_at')

    # Allowed sorting fields to prevent injection
    allowed_sorts = ['created_at', '-created_at', 'due_date', '-due_date', 'priority', '-priority', 'title', '-title']
    if sort_by not in allowed_sorts:
        sort_by = '-created_at'

    tasks = (
        Task.objects.filter(user=user)
        .exclude(status='archived')
        .select_related('category')
        .prefetch_related('subtasks')
    )

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
        # SMART CREATE (AI parser request)
        nl_input = request.POST.get('natural_language', '').strip()
        if nl_input:
            parsed = parse_natural_language_task(nl_input)
            initial = {
                'title': parsed.get('title', nl_input),
                'priority': parsed.get('priority', 'medium'),
            }
            if parsed.get('due_date'):
                from django.utils.dateparse import parse_datetime
                due = parse_datetime(parsed['due_date'])
                if due:
                    initial['due_date'] = due.strftime('%Y-%m-%dT%H:%M')

            # Match category by name if available
            cat_name = parsed.get('category')
            if cat_name and cat_name != 'Other':
                cat = Category.objects.filter(user=request.user, name__iexact=cat_name).first()
                if cat:
                    initial['category'] = cat.id

            form = TaskForm(initial=initial, user=request.user)
            subtask_suggestions = generate_subtasks(initial['title'])

            return render(request, 'tasks/task_form.html', {
                'form': form,
                'natural_language': nl_input,
                'subtask_suggestions': subtask_suggestions,
                'action': 'Create'
            })

        # STANDARD FORM SUBMISSION
        form = TaskForm(request.POST, user=request.user)
        if form.is_valid():
            task = form.save(commit=False)
            task.user = request.user
            task.save()

            # Process attached subtasks JSON
            subtasks_json = request.POST.get('subtasks_json', '[]')
            try:
                subtasks_list = json.loads(subtasks_json)
                if isinstance(subtasks_list, list):
                    for title in subtasks_list:
                        if isinstance(title, str) and title.strip():
                            SubTask.objects.create(task=task, title=title.strip())
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Error parsing subtasks_json: {e}")

            # Schedule reminder if set
            if task.reminder_at:
                Reminder.objects.create(task=task, remind_at=task.reminder_at)

            messages.success(request, "Task created successfully!")
            return redirect('task_list')
    else:
        form = TaskForm(user=request.user)

    return render(request, 'tasks/task_form.html', {
        'form': form,
        'action': 'Create',
        'subtask_suggestions': []
    })


@login_required
def task_update(request, pk):
    task = get_object_or_404(
        Task.objects.select_related('category').prefetch_related('subtasks'),
        pk=pk, 
        user=request.user
    )
    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task, user=request.user)
        if form.is_valid():
            task = form.save()

            # Synchronize reminder
            Reminder.objects.filter(task=task).delete()
            if task.reminder_at and task.status != 'completed':
                Reminder.objects.create(task=task, remind_at=task.reminder_at)

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
@require_POST
def task_toggle(request, pk):
    task = get_object_or_404(Task, pk=pk, user=request.user)
    if task.status == 'completed':
        task.status = 'pending'
        task.completed_at = None
    else:
        task.status = 'completed'
        task.completed_at = timezone.now()
        
        # If task is recurring, trigger recurrence check
        if task.is_recurring:
            try:
                from .tasks import process_recurring_tasks
                # Trigger task locally or async
                process_recurring_tasks.delay()
            except Exception:
                pass
                
    task.save()
    update_daily_analytics(request.user)

    return JsonResponse({
        'status': task.status,
        'completed_at': task.completed_at.isoformat() if task.completed_at else None
    })


@login_required
def task_archive(request, pk):
    task = get_object_or_404(Task, pk=pk, user=request.user)
    if request.method == 'POST':
        task.status = 'archived'
        task.save(update_fields=['status'])
        messages.success(request, f'Task "{task.title}" archived.')
        return redirect('task_list')
    return render(request, 'tasks/task_confirm_archive.html', {'task': task})


@login_required
def archived_tasks(request):
    tasks = (
        Task.objects.filter(user=request.user, status='archived')
        .select_related('category')
        .prefetch_related('subtasks')
        .order_by('-updated_at')
    )
    return render(request, 'tasks/archived_list.html', {'tasks': tasks})


@login_required
@require_POST
def subtask_create(request, task_pk):
    task = get_object_or_404(Task, pk=task_pk, user=request.user)
    title = request.POST.get('title', '').strip()
    
    # Try parsing JSON body if title not in form data
    if not title and request.body:
        try:
            data = json.loads(request.body)
            title = data.get('title', '').strip()
        except (json.JSONDecodeError, TypeError):
            pass

    if not title:
        return JsonResponse({'error': 'Title is required'}, status=400)

    subtask = SubTask.objects.create(task=task, title=title)
    return JsonResponse({'id': subtask.id, 'title': subtask.title})


@login_required
@require_POST
def subtask_toggle(request, pk):
    subtask = get_object_or_404(SubTask.objects.select_related('task'), pk=pk, task__user=request.user)
    subtask.is_completed = not subtask.is_completed
    subtask.save(update_fields=['is_completed'])

    # Auto-complete parent task if all subtasks are finished
    task = subtask.task
    all_subtasks = list(task.subtasks.all())
    all_done = bool(all_subtasks and all(s.is_completed for s in all_subtasks))
    if all_done and task.status != 'completed':
        task.status = 'completed'
        task.completed_at = timezone.now()
        task.save(update_fields=['status', 'completed_at'])
        update_daily_analytics(request.user)

    return JsonResponse({'is_completed': subtask.is_completed, 'all_done': all_done})


@login_required
@require_POST
def subtask_delete(request, pk):
    subtask = get_object_or_404(SubTask, pk=pk, task__user=request.user)
    subtask.delete()
    return JsonResponse({'success': True})


@login_required
def category_list(request):
    categories = Category.objects.filter(user=request.user).annotate(
        task_count=Count('tasks', filter=Q(tasks__user=request.user))
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

    total_tasks = Task.objects.filter(user=user).count()
    completed_tasks = Task.objects.filter(user=user, status='completed').count()
    pending_tasks = Task.objects.filter(user=user, status='pending').count()

    month_start = today.replace(day=1)
    monthly_completed = Task.objects.filter(
        user=user, 
        status='completed',
        completed_at__date__gte=month_start
    ).count()

    avg_time = Task.objects.filter(
        user=user, 
        status='completed',
        completed_at__isnull=False
    ).annotate(
        duration=F('completed_at') - F('created_at')
    ).aggregate(avg=Avg('duration'))['avg']

    priority_data = list(Task.objects.filter(user=user).values('priority').annotate(
        count=Count('id')
    ).order_by('priority'))

    week_data = []
    for i in range(6, -1, -1):
        date = today - timedelta(days=i)
        analytics_day = DailyAnalytics.objects.filter(user=user, date=date).first()
        week_data.append({
            'date': date.strftime('%a'),
            'created': analytics_day.tasks_created if analytics_day else 0,
            'completed': analytics_day.tasks_completed if analytics_day else 0,
        })

    category_data = list(Category.objects.filter(user=user).annotate(
        count=Count('tasks', filter=Q(tasks__user=user))
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


# ============================================================================
# PHASE 3: Web Push Subscriptions
# ============================================================================

@login_required
@require_POST
def push_subscribe(request):
    try:
        data = json.loads(request.body)
        endpoint = data.get('endpoint')
        keys = data.get('keys', {})
        p256dh = keys.get('p256dh')
        auth = keys.get('auth')

        if not endpoint or not p256dh or not auth:
            return JsonResponse({'error': 'Invalid subscription payload'}, status=400)

        PushSubscription.objects.update_or_create(
            endpoint=endpoint,
            defaults={
                'user': request.user,
                'p256dh': p256dh,
                'auth': auth,
            }
        )
        return JsonResponse({'status': 'subscribed'})
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Push subscribe error: {e}")
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def get_vapid_public_key(request):
    return JsonResponse({'publicKey': getattr(settings, 'VAPID_PUBLIC_KEY', '')})


# ============================================================================
# PHASE 4: Calendar Sync & Interactive FullCalendar.js View
# ============================================================================

@login_required
def calendar_view(request):
    categories = Category.objects.filter(user=request.user)
    return render(request, 'tasks/calendar.html', {'categories': categories})


@login_required
def calendar_events_api(request):
    user = request.user
    tasks = (
        Task.objects.filter(user=user)
        .exclude(status='archived')
        .filter(due_date__isnull=False)
        .select_related('category')
    )

    priority_colors = {
        'urgent': '#ef4444',
        'high': '#f97316',
        'medium': '#8b5cf6',
        'low': '#3b82f6',
    }

    events = []
    for t in tasks:
        color = t.category.color if t.category else priority_colors.get(t.priority, '#8b5cf6')
        events.append({
            'id': t.id,
            'title': t.title,
            'start': t.due_date.isoformat(),
            'backgroundColor': color,
            'borderColor': color,
            'url': f"/tasks/{t.id}/edit/",
            'extendedProps': {
                'priority': t.priority,
                'status': t.status,
                'category': t.category.name if t.category else 'No Category',
                'is_recurring': t.is_recurring,
            }
        })

    return JsonResponse(events, safe=False)


@login_required
@require_POST
def task_reschedule(request, pk):
    task = get_object_or_404(Task, pk=pk, user=request.user)
    try:
        data = json.loads(request.body)
        new_due_str = data.get('new_due_date')
        if not new_due_str:
            return JsonResponse({'error': 'New due date required'}, status=400)

        from django.utils.dateparse import parse_datetime
        new_due = parse_datetime(new_due_str)
        if not new_due:
            return JsonResponse({'error': 'Invalid date format'}, status=400)

        task.due_date = new_due
        task.save(update_fields=['due_date'])
        return JsonResponse({'success': True, 'new_due_date': task.due_date.isoformat()})
    except (json.JSONDecodeError, Exception) as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def export_tasks_ics(request):
    """Export user's scheduled tasks as an iCalendar (.ics) file."""
    try:
        from icalendar import Calendar, Event, vDatetime
        cal = Calendar()
        cal.add('prodid', '-//TaskFlow Productivity//EN')
        cal.add('version', '2.0')
        cal.add('x-wr-calname', f'TaskFlow - {request.user.username}')

        tasks = (
            Task.objects.filter(user=request.user, due_date__isnull=False)
            .exclude(status='archived')
            .select_related('category')
        )

        for t in tasks:
            event = Event()
            event.add('summary', t.title)
            if t.description:
                event.add('description', t.description)
            event.add('dtstart', t.due_date)
            event.add('dtend', t.due_date + timedelta(hours=1))
            event.add('dtstamp', timezone.now())
            event.add('uid', f'taskflow-{t.id}@{request.get_host()}')
            if t.category:
                event.add('categories', [t.category.name])
            cal.add_component(event)

        response = HttpResponse(cal.to_ical(), content_type='text/calendar; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="tasks.ics"'
        return response
    except Exception as e:
        logger.error(f"iCal export failed: {e}")
        messages.error(request, "Failed to generate iCal export.")
        return redirect('task_list')


def update_daily_analytics(user):
    """Update or create daily analytics record."""
    today = timezone.now().date()
    created_count = Task.objects.filter(user=user, created_at__date=today).count()
    completed_count = Task.objects.filter(user=user, completed_at__date=today).count()
    overdue_count = Task.objects.filter(
        user=user, 
        due_date__date__lt=today, 
        status__in=['pending', 'in_progress']
    ).count()

    analytics, created = DailyAnalytics.objects.get_or_create(
        user=user,
        date=today,
        defaults={
            'tasks_created': created_count,
            'tasks_completed': completed_count,
            'tasks_overdue': overdue_count,
            'completion_rate': round((completed_count / created_count * 100), 1) if created_count > 0 else 0
        }
    )
    if not created:
        analytics.tasks_created = created_count
        analytics.tasks_completed = completed_count
        analytics.tasks_overdue = overdue_count
        analytics.completion_rate = round((completed_count / created_count * 100), 1) if created_count > 0 else 0
        analytics.save()
