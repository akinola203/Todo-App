import os
import json
import random
from datetime import datetime, timedelta
from django.utils import timezone
import google.generativeai as genai

genai.configure(api_key=os.environ.get('GEMINI_API_KEY'))

class TaskFlowAI:
    NAME = "Nova"
    GREETINGS = {
        'morning': [
            "Rise and grind! Your tasks are waiting.",
            "Good morning! Let's make today count.",
            "The early bird gets the... completed task list!"
        ],
        'afternoon': [
            "Afternoon energy check! Still got it?",
            "Halfway through the day — how we doing?",
            "Lunch break over? Time to dominate."
        ],
        'evening': [
            "Evening mode! Let's wrap up strong.",
            "Night owl detected. Let's clear that list.",
            "Almost there — finish what you started."
        ]
    }
    ENCOURAGEMENT = {
        'on_fire': [
            "You're on FIRE! Keep this streak alive!",
            "Absolute machine today. I'm impressed.",
            "Who IS this productivity beast?!"
        ],
        'doing_well': [
            "Solid progress. One more and you're golden.",
            "Steady wins the race. Keep it up!",
            "Nice rhythm you've got going."
        ],
        'needs_push': [
            "I believe in you. Knock one out.",
            "That task is smaller than it looks. Trust me.",
            "5 minutes of focus. That's all I'm asking."
        ],
        'struggling': [
            "Hey, rough days happen. Start with ONE tiny task.",
            "Overwhelmed? Let's break this down together.",
            "Progress, not perfection. You've got this."
        ]
    }
    ROASTS = [
        "That task is collecting dust like a museum piece.",
        "I've seen glaciers move faster than this task list.",
        "Procrastination called. It wants its crown back.",
        "This task is so old it qualifies for a pension.",
        "Your future self is BEGGING you to do this."
    ]

def get_time_of_day():
    hour = datetime.now().hour
    if hour < 12: return 'morning'
    elif hour < 17: return 'afternoon'
    else: return 'evening'

def get_user_mood(user):
    from .models import Task
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    recent_completed = Task.objects.filter(user=user, status='completed', completed_at__date__gte=week_ago).count()
    overdue = Task.objects.filter(user=user, status__in=['pending', 'in_progress'], due_date__lt=timezone.now()).count()
    if recent_completed >= 5 and overdue == 0: return 'on_fire'
    elif recent_completed >= 3: return 'doing_well'
    elif overdue >= 3: return 'struggling'
    else: return 'doing_well'

def get_ai_greeting(user):
    from .models import Task
    time_of_day = get_time_of_day()
    mood = get_user_mood(user)
    ai = TaskFlowAI()
    greeting = random.choice(ai.GREETINGS[time_of_day])
    encouragement = random.choice(ai.ENCOURAGEMENT[mood])
    streak = 0
    check_date = timezone.now().date()
    while Task.objects.filter(user=user, completed_at__date=check_date).exists():
        streak += 1
        check_date -= timedelta(days=1)
    streak_msg = f"🔥 {streak}-day streak!" if streak > 1 else ""
    return {'name': ai.NAME, 'greeting': greeting, 'encouragement': encouragement, 'streak_msg': streak_msg, 'mood': mood}

def get_procrastination_alert(user):
    from .models import Task
    old_tasks = Task.objects.filter(user=user, status='pending', created_at__lt=timezone.now() - timedelta(days=3)).order_by('created_at')[:3]
    if not old_tasks: return None
    task = old_tasks[0]
    ai = TaskFlowAI()
    return {'task_title': task.title, 'days_old': (timezone.now() - task.created_at).days, 'roast': random.choice(ai.ROASTS), 'suggestion': f"Want me to break '{task.title}' into smaller steps?"}

def get_smart_schedule_tip(user):
    from .models import Task
    completed = Task.objects.filter(user=user, status='completed', completed_at__isnull=False)
    if completed.count() < 5: return "Complete a few more tasks and I'll learn your peak hours!"
    peak_hour = 9
    try:
        hour_counts = {}
        for t in completed:
            h = t.completed_at.hour
            hour_counts[h] = hour_counts.get(h, 0) + 1
        peak_hour = max(hour_counts, key=hour_counts.get)
    except: pass
    current_hour = datetime.now().hour
    urgent = Task.objects.filter(user=user, priority='urgent', status__in=['pending', 'in_progress']).first()
    if urgent and current_hour == peak_hour: return f"🔥 Peak performance hour! Perfect time for '{urgent.title}'"
    elif urgent: return f"⏰ '{urgent.title}' is urgent. Your peak hour is {peak_hour}:00 — plan around it!"
    return None

def get_xp_and_level(user):
    from .models import Task
    completed = Task.objects.filter(user=user, status='completed').count()
    urgent_done = Task.objects.filter(user=user, status='completed', priority='urgent').count()
    xp = (completed * 10) + (urgent_done * 25)
    level = (xp // 100) + 1
    progress = xp % 100
    titles = {1: "Task Rookie", 2: "Productivity Padawan", 3: "Focus Warrior", 4: "Efficiency Ninja", 5: "Task Master", 6: "Productivity Legend", 7: "Completion God"}
    return {'xp': xp, 'level': level, 'title': titles.get(min(level, 7), "Ultimate Legend"), 'progress': progress, 'next_level': level * 100, 'completed_count': completed}

VALID_PRIORITIES = ['low', 'medium', 'high', 'urgent']

def normalize_priority(value):
    if not value: return 'medium'
    value = str(value).lower().strip()
    if value in ['low', 'l']: return 'low'
    if value in ['medium', 'med', 'm', 'normal']: return 'medium'
    if value in ['high', 'h', 'important']: return 'high'
    if value in ['urgent', 'u', 'critical', 'asap']: return 'urgent'
    return 'medium'

def normalize_category(value):
    if not value: return 'Other'
    value = str(value).strip()
    cats = ['Work', 'Personal', 'Health', 'Finance', 'Shopping', 'Learning', 'Other']
    for cat in cats:
        if cat.lower() == value.lower(): return cat
    return 'Other'

def parse_natural_language_task(text):
    today = datetime.now().strftime('%Y-%m-%d')
    prompt = f"""Today is {today}. Parse this task into JSON: \"{text}\"
    Return ONLY valid JSON with: title, due_date (ISO or null), priority (low/medium/high/urgent), category (Work/Personal/Health/Finance/Shopping/Learning/Other)
    Example: {{\"title\": \"Submit report\", \"due_date\": \"2026-08-14T17:00:00\", \"priority\": \"high\", \"category\": \"Work\"}}"""
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        raw_text = response.text.strip()
        for p in ['```json', '```']:
            if raw_text.startswith(p): raw_text = raw_text[len(p):]
        if raw_text.endswith('```'): raw_text = raw_text[:-3]
        result = json.loads(raw_text.strip())
        result['priority'] = normalize_priority(result.get('priority'))
        result['category'] = normalize_category(result.get('category'))
        if not result.get('title'): result['title'] = text
        return result
    except Exception as e:
        print(f"AI parse failed: {e}")
        return {'title': text, 'due_date': None, 'priority': 'medium', 'category': 'Other'}

def generate_subtasks(task_title, task_description=''):
    prompt = f"""Break this task into 3-5 specific subtasks: Task: \"{task_title}\" Description: \"{task_description}\"
    Return ONLY a JSON array of strings. Example: [\"Research topic\", \"Write outline\"]"""
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        raw_text = response.text.strip()
        for p in ['```json', '```']:
            if raw_text.startswith(p): raw_text = raw_text[len(p):]
        if raw_text.endswith('```'): raw_text = raw_text[:-3]
        return json.loads(raw_text.strip())
    except:
        return []
