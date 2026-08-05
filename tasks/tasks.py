from celery import shared_task
from django.core.mail import send_mail
from django.utils import timezone
from django.contrib.auth.models import User
from .models import Task, Reminder, DailyAnalytics


@shared_task
def check_and_send_reminders():
    """Check for due reminders and send notifications."""
    now = timezone.now()
    reminders = Reminder.objects.filter(
        remind_at__lte=now,
        remind_at__gte=now - timezone.timedelta(minutes=5),
        is_sent=False
    ).select_related('task', 'task__user')

    for reminder in reminders:
        task = reminder.task
        user = task.user

        # Send email notification
        try:
            send_mail(
                subject=f'Reminder: {task.title}',
                message=f'Hi {user.username},\n\nThis is a reminder for your task: "{task.title}"\nDue: {task.due_date}\nPriority: {task.priority}\n\n- TaskFlow',
                from_email='noreply@taskflow.app',
                recipient_list=[user.email],
                fail_silently=True,
            )
            reminder.is_sent = True
            reminder.save()
        except Exception as e:
            print(f"Failed to send reminder for task {task.id}: {e}")

    return f"Processed {reminders.count()} reminders"


@shared_task
def update_all_daily_analytics():
    """Update analytics for all users at end of day."""
    today = timezone.now().date()
    for user in User.objects.all():
        analytics, created = DailyAnalytics.objects.get_or_create(
            user=user,
            date=today,
            defaults={
                'tasks_created': Task.objects.filter(user=user, created_at__date=today).count(),
                'tasks_completed': Task.objects.filter(user=user, completed_at__date=today).count(),
                'tasks_overdue': Task.objects.filter(
                    user=user, 
                    due_date__date__lt=today, 
                    status__in=['pending', 'in_progress']
                ).count(),
            }
        )
        if not created:
            analytics.tasks_created = Task.objects.filter(user=user, created_at__date=today).count()
            analytics.tasks_completed = Task.objects.filter(user=user, completed_at__date=today).count()
            analytics.tasks_overdue = Task.objects.filter(
                user=user, 
                due_date__date__lt=today, 
                status__in=['pending', 'in_progress']
            ).count()

        total = analytics.tasks_created
        analytics.completion_rate = round((analytics.tasks_completed / total * 100), 1) if total > 0 else 0
        analytics.save()

    return "Daily analytics updated for all users"


@shared_task
def cleanup_old_reminders():
    """Delete reminders older than 30 days."""
    cutoff = timezone.now() - timezone.timedelta(days=30)
    deleted = Reminder.objects.filter(remind_at__lt=cutoff).delete()
    return f"Deleted {deleted[0]} old reminders"
