import json
from datetime import timedelta, date
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

    def test_instant_demo(self):
        """Guest user can click 'Try Instant Demo' to auto-seed starter categories and tasks."""
        self.client.logout()
        res = self.client.get(reverse('instant_demo'))
        self.assertEqual(res.status_code, 302)
        self.assertRedirects(res, reverse('dashboard'))

        # Verify demo user has General, Meetings, and Trip groups with tasks
        demo_user = User.objects.get(username='demo_guest')
        self.assertTrue(Category.objects.filter(user=demo_user, name='General').exists())
        self.assertTrue(Category.objects.filter(user=demo_user, name='Meetings').exists())
        self.assertTrue(Category.objects.filter(user=demo_user, name='Trip').exists())
        self.assertTrue(Task.objects.filter(user=demo_user, title__icontains="Amanda").exists())
        self.assertTrue(Task.objects.filter(user=demo_user, title__icontains="Norway").exists())


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


class SecurityAuditTests(TestCase):
    def setUp(self):
        self.client_a = Client()
        self.user_a = User.objects.create_user(username='usera', password='UserA_Password123!', email='usera@example.com')
        self.client_a.login(username='usera', password='UserA_Password123!')

        self.client_b = Client()
        self.user_b = User.objects.create_user(username='userb', password='UserB_Password123!', email='userb@example.com')
        self.client_b.login(username='userb', password='UserB_Password123!')

        self.cat_a = Category.objects.create(name='Private A', user=self.user_a, color='#123456')
        self.task_a = Task.objects.create(user=self.user_a, title='User A Task', category=self.cat_a)
        self.subtask_a = SubTask.objects.create(task=self.task_a, title='Private Subtask')

    def test_unauthenticated_access_redirects_to_login(self):
        anon_client = Client()
        protected_urls = [
            reverse('dashboard'),
            reverse('task_list'),
            reverse('calendar_view'),
            reverse('analytics'),
            reverse('category_list'),
            reverse('task_create'),
        ]
        for url in protected_urls:
            res = anon_client.get(url)
            self.assertEqual(res.status_code, 302, f"URL {url} should redirect unauthenticated users to login")
            self.assertIn(reverse('login'), res.url)

    def test_idor_task_endpoints_prevent_cross_user_access(self):
        # User B attempts to edit User A's task -> 404
        res_edit = self.client_b.get(reverse('task_update', args=[self.task_a.id]))
        self.assertEqual(res_edit.status_code, 404)

        # User B attempts to delete User A's task -> 404
        res_del = self.client_b.post(reverse('task_delete', args=[self.task_a.id]))
        self.assertEqual(res_del.status_code, 404)

        # User B attempts to toggle User A's task -> 404
        res_toggle = self.client_b.post(reverse('task_toggle', args=[self.task_a.id]))
        self.assertEqual(res_toggle.status_code, 404)

        # User B attempts to archive User A's task -> 404
        res_archive = self.client_b.post(reverse('task_archive', args=[self.task_a.id]))
        self.assertEqual(res_archive.status_code, 404)

        # User B attempts to reschedule User A's task -> 404
        res_resched = self.client_b.post(
            reverse('task_reschedule', args=[self.task_a.id]),
            data=json.dumps({'new_due_date': '2026-12-01T12:00:00Z'}),
            content_type='application/json'
        )
        self.assertEqual(res_resched.status_code, 404)

    def test_idor_subtask_and_category_endpoints(self):
        # User B attempts to toggle User A's subtask -> 404
        res_sub_toggle = self.client_b.post(reverse('subtask_toggle', args=[self.subtask_a.id]))
        self.assertEqual(res_sub_toggle.status_code, 404)

        # User B attempts to delete User A's subtask -> 404
        res_sub_del = self.client_b.post(reverse('subtask_delete', args=[self.subtask_a.id]))
        self.assertEqual(res_sub_del.status_code, 404)

        # User B attempts to create subtask under User A's task -> 404
        res_sub_create = self.client_b.post(reverse('subtask_create', args=[self.task_a.id]), {'title': 'Hacked'})
        self.assertEqual(res_sub_create.status_code, 404)

        # User B attempts to delete User A's category -> 404
        res_cat_del = self.client_b.post(reverse('category_delete', args=[self.cat_a.id]))
        self.assertEqual(res_cat_del.status_code, 404)

    def test_prevent_assigning_other_users_category(self):
        from .forms import TaskForm
        # User B tries to submit a task with User A's category ID
        form = TaskForm(
            data={'title': 'User B Task', 'category': self.cat_a.id, 'priority': 'medium', 'status': 'pending'},
            user=self.user_b
        )
        self.assertFalse(form.is_valid())
        self.assertIn('category', form.errors)

    def test_category_form_input_sanitization(self):
        from .forms import CategoryForm
        # Invalid hex color rejected
        form = CategoryForm(data={'name': 'Test', 'color': 'not-a-hex', 'icon': 'fa-tag'})
        self.assertFalse(form.is_valid())
        self.assertIn('color', form.errors)

        # Invalid icon format rejected
        form2 = CategoryForm(data={'name': 'Test', 'color': '#ff0000', 'icon': 'fa-tag; alert(1)'})
        self.assertFalse(form2.is_valid())
        self.assertIn('icon', form2.errors)

        # Valid input accepted
        form3 = CategoryForm(data={'name': 'Valid Cat', 'color': '#8b5cf6', 'icon': 'fa-check'})
        self.assertTrue(form3.is_valid())


class TaskSecurityTestCase(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.client = Client()
        
        # Create two distinct users to test multi-tenant data isolation
        self.victim = User.objects.create_user(username='victim', password='StrongPassword123!')
        self.attacker = User.objects.create_user(username='attacker', password='StrongPassword123!')

        # Create victim's private resources
        self.victim_category = Category.objects.create(
            user=self.victim, 
            name='Confidential Project', 
            color='#dc2626'
        )
        self.victim_task = Task.objects.create(
            user=self.victim,
            title='Acquire Competitor',
            priority='urgent',
            status='pending',
            category=self.victim_category,
            due_date=date(2026, 12, 31)
        )
        self.victim_subtask = SubTask.objects.create(
            task=self.victim_task,
            title='Draft acquisition terms',
            is_completed=False
        )

    def tearDown(self):
        from django.core.cache import cache
        cache.clear()
        super().tearDown()

    def test_unauthenticated_access_blocked(self):
        """Ensure anonymous requests to pages and APIs redirect to login."""
        protected_urls = [
            reverse('dashboard'),
            reverse('task_list'),
            reverse('calendar_view'),
            reverse('calendar_events_api'),
            reverse('export_tasks_ics'),
            reverse('task_update', args=[self.victim_task.id]),
        ]
        for url in protected_urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, f"Unprotected GET route: {url}")
            self.assertIn('/login/', response.url)

    def test_idor_task_detail_and_update_isolation(self):
        """Attacker cannot view or edit Victim's task via direct URL."""
        self.client.login(username='attacker', password='StrongPassword123!')
        
        update_url = reverse('task_update', args=[self.victim_task.id])
        
        # Attempt GET
        get_res = self.client.get(update_url)
        self.assertEqual(get_res.status_code, 404)

        # Attempt POST overwrite
        post_res = self.client.post(update_url, {
            'title': 'Pwned Task',
            'priority': 'low',
            'status': 'completed'
        })
        self.assertEqual(post_res.status_code, 404)
        
        self.victim_task.refresh_from_db()
        self.assertEqual(self.victim_task.title, 'Acquire Competitor')

    def test_idor_ajax_task_toggle_and_reschedule_isolation(self):
        """Attacker cannot toggle status or reschedule Victim's task via AJAX."""
        self.client.login(username='attacker', password='StrongPassword123!')

        # 1. Test Task Toggle
        toggle_url = reverse('task_toggle', args=[self.victim_task.id])
        toggle_res = self.client.post(toggle_url, content_type='application/json')
        self.assertIn(toggle_res.status_code, [403, 404])
        
        self.victim_task.refresh_from_db()
        self.assertEqual(self.victim_task.status, 'pending')

        # 2. Test Calendar Drag-and-Drop Reschedule
        reschedule_url = reverse('task_reschedule_api', args=[self.victim_task.id])
        reschedule_res = self.client.post(
            reschedule_url,
            data=json.dumps({'due_date': '2027-05-01'}),
            content_type='application/json'
        )
        self.assertIn(reschedule_res.status_code, [400, 403, 404])
        
        self.victim_task.refresh_from_db()
        self.assertEqual(self.victim_task.due_date, date(2026, 12, 31))

    def test_idor_subtask_manipulation_isolation(self):
        """Attacker cannot create, toggle, or delete subtasks on Victim's task."""
        self.client.login(username='attacker', password='StrongPassword123!')

        # 1. Inject subtask into Victim's task
        create_url = reverse('subtask_create', args=[self.victim_task.id])
        create_res = self.client.post(
            create_url,
            data=json.dumps({'title': 'Injected Subtask'}),
            content_type='application/json'
        )
        self.assertIn(create_res.status_code, [403, 404])
        self.assertEqual(self.victim_task.subtasks.count(), 1)

        # 2. Toggle Victim's subtask
        toggle_url = reverse('subtask_toggle', args=[self.victim_subtask.id])
        toggle_res = self.client.post(toggle_url, content_type='application/json')
        self.assertIn(toggle_res.status_code, [403, 404])
        self.victim_subtask.refresh_from_db()
        self.assertFalse(self.victim_subtask.is_completed)

        # 3. Delete Victim's subtask
        delete_url = reverse('subtask_delete', args=[self.victim_subtask.id])
        delete_res = self.client.post(delete_url, content_type='application/json')
        self.assertIn(delete_res.status_code, [403, 404])
        self.assertTrue(SubTask.objects.filter(id=self.victim_subtask.id).exists())

    def test_foreign_category_assignment_prevented(self):
        """Attacker cannot bind a new task to Victim's private Category ID."""
        self.client.login(username='attacker', password='StrongPassword123!')
        
        create_url = reverse('task_create')
        self.client.post(create_url, {
            'title': 'Attacker Task',
            'priority': 'medium',
            'status': 'pending',
            'category': self.victim_category.id  # Attempting foreign key injection
        })
        
        # Form validation should reject the foreign category ID
        attacker_task = Task.objects.filter(user=self.attacker, title='Attacker Task').first()
        if attacker_task:
            self.assertNotEqual(attacker_task.category, self.victim_category)

    def test_calendar_and_ical_feed_data_leakage(self):
        """Calendar JSON feed and .ics export must never leak another user's tasks."""
        self.client.login(username='attacker', password='StrongPassword123!')

        # Check FullCalendar JSON API
        cal_res = self.client.get(reverse('calendar_events_api'))
        self.assertEqual(cal_res.status_code, 200)
        events = json.loads(cal_res.content)
        self.assertEqual(len(events), 0)

        # Check iCal .ics file download
        ics_res = self.client.get(reverse('export_tasks_ics'))
        self.assertEqual(ics_res.status_code, 200)
        self.assertNotIn(b'Acquire Competitor', ics_res.content)

    def test_csrf_enforcement_on_mutating_endpoints(self):
        """Ensure POST endpoints reject requests missing a valid CSRF token."""
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.login(username='victim', password='StrongPassword123!')

        toggle_url = reverse('task_toggle', args=[self.victim_task.id])
        res = csrf_client.post(toggle_url, content_type='application/json')
        self.assertEqual(res.status_code, 403)

    def test_rate_limit_login_brute_force(self):
        """Sending 5 failed POSTs to login succeeds with 200, and the 6th POST returns HTTP 429."""
        login_url = reverse('login')
        for _ in range(5):
            res = self.client.post(login_url, {'username': 'wronguser', 'password': 'wrongpassword'})
            self.assertEqual(res.status_code, 200)

        # 6th attempt triggers HTTP 429
        blocked_res = self.client.post(login_url, {'username': 'wronguser', 'password': 'wrongpassword'})
        self.assertEqual(blocked_res.status_code, 429)

    def test_rate_limit_ai_task_create(self):
        """Exceeding 10 POST requests per minute on the AI task creation endpoint returns HTTP 429."""
        self.client.login(username='victim', password='StrongPassword123!')
        create_url = reverse('task_create')

        for i in range(10):
            res = self.client.post(create_url, {'natural_language': f'Task {i} tomorrow urgent'})
            self.assertIn(res.status_code, [200, 302])

        # 11th attempt (exceeding 10) returns HTTP 429
        blocked_res = self.client.post(create_url, {'natural_language': 'Over quota task'})
        self.assertEqual(blocked_res.status_code, 429)

