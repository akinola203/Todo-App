import os
import json
import logging
from datetime import timedelta
try:
    from celery import shared_task
except ImportError:
    def shared_task(*args, **kwargs):
        def decorator(func):
            func.delay = lambda *a, **k: func(*a, **k)
            return func
        if args and callable(args[0]):
            return decorator(args[0])
        return decorator

from django.core.mail import send_mail
from django.utils import timezone
from django.contrib.auth.models import User
from django.conf import settings
from .models import Task, SubTask, Reminder, DailyAnalytics, PushSubscription

logger = logging.getLogger(__name__)

def send_web_push(subscription, payload):
    """Deliver a web push notification via pywebpush."""
    try:
        from pywebpush import webpush, WebPushException
        vapid_private_key = getattr(settings, 'VAPID_PRIVATE_KEY', None)
        vapid_claims = {
            "sub": f"mailto:{getattr(settings, 'VAPID_ADMIN_EMAIL', 'admin@taskflow.app')}"
        }
        if not vapid_private_key:
            return False

        subscription_info = {
            "endpoint": subscription.endpoint,
            "keys": {
                "p256dh": subscription.p256dh,
                "auth": subscription.auth
            }
        }
        webpush(
            subscription_info=subscription_info,
            data=json.dumps(payload),
            vapid_private_key=vapid_private_key,
            vapid_claims=vapid_claims,
            ttl=86400
        )
        return True
    except Exception as e:
        logger.warning(f"Push send failed for endpoint {subscription.endpoint[:30]}...: {e}")
        return False


@shared_task
def check_and_send_reminders():
    """Check for due reminders and send email and web push notifications."""
    now = timezone.now()
    reminders = Reminder.objects.filter(
        remind_at__lte=now,
        remind_at__gte=now - timedelta(minutes=15),
        is_sent=False
    ).select_related('task', 'task__user')

    count = 0
    for reminder in reminders:
        task = reminder.task
        user = task.user

        # 1. Send email notification
        try:
            if user.email:
                send_mail(
                    subject=f'Task Reminder: {task.title}',
                    message=f'Hi {user.username},\n\nReminder for your task: "{task.title}"\nDue: {task.due_date}\nPriority: {task.get_priority_display()}\n\nTaskFlow App',
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@taskflow.app'),
                    recipient_list=[user.email],
                    fail_silently=True,
                )
        except Exception as e:
            logger.error(f"Email reminder failed for task {task.id}: {e}")

        # 2. Send Web Push notification
        push_subs = PushSubscription.objects.filter(user=user)
        for sub in push_subs:
            send_web_push(sub, {
                'title': f'⏰ Task Reminder: {task.title}',
                'body': f'Due: {task.due_date.strftime("%b %d, %H:%M") if task.due_date else "Soon"} | Priority: {task.priority.capitalize()}',
                'url': f'/tasks/{task.id}/edit/'
            })

        reminder.is_sent = True
        reminder.save(update_fields=['is_sent'])
        count += 1

    return f"Processed {count} reminders"


@shared_task
def process_recurring_tasks():
    """Spawns the next iteration for completed recurring tasks."""
    completed_recurring = Task.objects.filter(
        is_recurring=True,
        status='completed'
    ).select_related('category', 'user').prefetch_related('subtasks')

    spawned_count = 0
    now = timezone.now()

    for task in completed_recurring:
        interval = task.recurrence_interval
        base_date = task.due_date if task.due_date else now
        
        if interval == 'daily':
            next_due = base_date + timedelta(days=1)
        elif interval == 'weekly':
            next_due = base_date + timedelta(weeks=1)
        elif interval == 'monthly':
            next_due = base_date + timedelta(days=30)
        else:
            continue

        # Prevent duplicate future creation if already spawned
        already_spawned = Task.objects.filter(
            user=task.user,
            title=task.title,
            due_date=next_due,
            status__in=['pending', 'in_progress']
        ).exists()

        if not already_spawned:
            new_task = Task.objects.create(
                user=task.user,
                title=task.title,
                description=task.description,
                priority=task.priority,
                status='pending',
                category=task.category,
                due_date=next_due,
                reminder_at=next_due - timedelta(hours=1) if task.reminder_at else None,
                is_pinned=task.is_pinned,
                is_recurring=True,
                recurrence_interval=task.recurrence_interval,
                tags=task.tags,
            )

            # Copy subtasks in uncompleted state
            for st in task.subtasks.all():
                SubTask.objects.create(
                    task=new_task,
                    title=st.title,
                    is_completed=False
                )

            # Mark previous task recurrence as inactive so it does not trigger again
            task.is_recurring = False
            task.save(update_fields=['is_recurring'])
            spawned_count += 1

    return f"Spawned {spawned_count} recurring tasks"


@shared_task
def update_all_daily_analytics():
    """Update analytics for all users at end of day."""
    today = timezone.now().date()
    for user in User.objects.all():
        created_count = Task.objects.filter(user=user, created_at__date=today).count()
        completed_count = Task.objects.filter(user=user, completed_at__date=today).count()
        overdue_count = Task.objects.filter(
            user=user, 
            due_date__date__lt=today, 
            status__in=['pending', 'in_progress']
        ).count()

        analytics, _ = DailyAnalytics.objects.get_or_create(
            user=user,
            date=today,
            defaults={
                'tasks_created': created_count,
                'tasks_completed': completed_count,
                'tasks_overdue': overdue_count,
                'completion_rate': round((completed_count / created_count * 100), 1) if created_count > 0 else 0
            }
        )
        analytics.tasks_created = created_count
        analytics.tasks_completed = completed_count
        analytics.tasks_overdue = overdue_count
        analytics.completion_rate = round((completed_count / created_count * 100), 1) if created_count > 0 else 0
        analytics.save()

    return "Daily analytics updated for all users"


@shared_task
def cleanup_old_reminders():
    """Delete reminders older than 30 days."""
    cutoff = timezone.now() - timedelta(days=30)
    deleted = Reminder.objects.filter(remind_at__lt=cutoff).delete()
    return f"Deleted {deleted[0]} old reminders"
