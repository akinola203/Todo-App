import json
from datetime import timedelta
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse

from .models import Task, SubTask, Category, Reminder, DailyAnalytics, PushSubscription
from .ai_utils import (
    parse_natural_language_task,
    generate_subtasks,
    get_xp_and_level,
    get_user_mood,
    get_ai_greeting,
    extract_json_block
)
from .tasks import process_recurring_tasks, update_all_daily_analytics


class TaskFlowModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.category = Category.objects.create(name='Work', user=self.user, color='#8b5cf6')

    def test_task_creation_and_properties(self):
        now = timezone.now()
        task = Task.objects.create(
            user=self.user,
            title='Test Task',
            category=self.category,
            priority='high',
            due_date=now - timedelta(hours=2),
            is_recurring=True,
            recurrence_interval='weekly'
        )
        self.assertTrue(task.is_overdue)
        self.assertFalse(task.is_due_soon)
        self.assertIsNone(task.completed_at)

        # Toggle to completed
        task.status = 'completed'
        task.save()
        self.assertIsNotNone(task.completed_at)
        self.assertFalse(task.is_overdue)

    def test_subtask_and_category(self):
        task = Task.objects.create(user=self.user, title='Main Task')
        subtask = SubTask.objects.create(task=task, title='Subtask 1')
        self.assertEqual(task.subtasks.count(), 1)
        self.assertFalse(subtask.is_completed)

    def test_push_subscription_creation(self):
        sub = PushSubscription.objects.create(
            user=self.user,
            endpoint='https://fcm.googleapis.com/fcm/send/fake-endpoint',
            p256dh='fake-key',
            auth='fake-auth'
        )
        self.assertEqual(self.user.push_subscriptions.count(), 1)
        self.assertEqual(sub.user, self.user)


class TaskFlowViewsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='johndoe', password='securepass123')
        self.client.login(username='johndoe', password='securepass123')
        self.category = Category.objects.create(name='Dev', user=self.user)

    def test_dashboard_authenticated(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dashboard')
        self.assertContains(response, 'Nova')

    def test_task_crud_and_toggle(self):
        # Create
        create_res = self.client.post(reverse('task_create'), {
            'title': 'New Feature Task',
            'priority': 'medium',
            'status': 'pending',
            'category': self.category.id,
            'subtasks_json': json.dumps(['Step 1', 'Step 2'])
        })
        self.assertEqual(create_res.status_code, 302)
        task = Task.objects.get(title='New Feature Task')
        self.assertEqual(task.subtasks.count(), 2)

        # Toggle via AJAX
        toggle_res = self.client.post(reverse('task_toggle', args=[task.id]))
        self.assertEqual(toggle_res.status_code, 200)
        data = toggle_res.json()
        self.assertEqual(data['status'], 'completed')
        self.assertIsNotNone(data['completed_at'])

    def test_calendar_and_export_views(self):
        now = timezone.now()
        task = Task.objects.create(
            user=self.user,
            title='Meeting',
            due_date=now + timedelta(days=1),
            priority='urgent',
            category=self.category
        )

        # Calendar HTML view
        cal_res = self.client.get(reverse('calendar_view'))
        self.assertEqual(cal_res.status_code, 200)

        # Calendar Events API
        events_res = self.client.get(reverse('calendar_events_api'))
        self.assertEqual(events_res.status_code, 200)
        events = events_res.json()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['title'], 'Meeting')

        # Reschedule API
        new_date = (now + timedelta(days=3)).isoformat()
        reschedule_res = self.client.post(
            reverse('task_reschedule', args=[task.id]),
            data=json.dumps({'new_due_date': new_date}),
            content_type='application/json'
        )
        self.assertEqual(reschedule_res.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.due_date.date(), (now + timedelta(days=3)).date())

        # iCal Export Feed
        ics_res = self.client.get(reverse('export_tasks_ics'))
        self.assertEqual(ics_res.status_code, 200)
        self.assertEqual(ics_res['Content-Type'], 'text/calendar; charset=utf-8')
        self.assertIn(b'Meeting', ics_res.content)

    def test_web_push_subscription_api(self):
        payload = {
            'endpoint': 'https://push.example.com/sub/12345',
            'keys': {
                'p256dh': 'test-p256dh',
                'auth': 'test-auth'
            }
        }
        res = self.client.post(
            reverse('push_subscribe'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(PushSubscription.objects.filter(endpoint=payload['endpoint']).exists())

    def test_task_archive_view(self):
        task = Task.objects.create(user=self.user, title='To Archive')
        # GET renders confirmation template
        get_res = self.client.get(reverse('task_archive', args=[task.id]))
        self.assertEqual(get_res.status_code, 200)
        self.assertTemplateUsed(get_res, 'tasks/task_confirm_archive.html')

        # POST archives task
        post_res = self.client.post(reverse('task_archive', args=[task.id]))
        self.assertEqual(post_res.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.status, 'archived')


class AIUtilsAndCeleryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='gamifieduser', password='pass')

    def test_json_extractor(self):
        markdown_json = "```json\n{\"title\": \"Buy groceries\", \"priority\": \"low\"}\n```"
        extracted = extract_json_block(markdown_json)
        data = json.loads(extracted)
        self.assertEqual(data['title'], 'Buy groceries')

    def test_fallback_natural_language_parser(self):
        parsed = parse_natural_language_task("Urgent client presentation prep")
        self.assertEqual(parsed['priority'], 'urgent')
        self.assertEqual(parsed['title'], "Urgent client presentation prep")

    def test_gamification_xp_calculation(self):
        Task.objects.create(user=self.user, title='Done 1', status='completed')
        Task.objects.create(user=self.user, title='Done Urgent', status='completed', priority='urgent')
        stats = get_xp_and_level(self.user)
        # 10 (normal done) + 35 (urgent done: 10 + 25) = 45 XP
        self.assertEqual(stats['xp'], 45)
        self.assertEqual(stats['level'], 1)

    def test_process_recurring_tasks(self):
        now = timezone.now()
        task = Task.objects.create(
            user=self.user,
            title='Weekly Clean',
            status='completed',
            is_recurring=True,
            recurrence_interval='weekly',
            due_date=now
        )
        SubTask.objects.create(task=task, title='Vacuum', is_completed=True)

        result = process_recurring_tasks()
        self.assertIn('Spawned 1 recurring tasks', result)

        # Check that the new iteration was created
        new_task = Task.objects.filter(user=self.user, status='pending', title='Weekly Clean').first()
        self.assertIsNotNone(new_task)
        self.assertTrue(new_task.is_recurring)
        self.assertEqual(new_task.recurrence_interval, 'weekly')
        self.assertEqual(new_task.subtasks.count(), 1)
        self.assertFalse(new_task.subtasks.first().is_completed)

