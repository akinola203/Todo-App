import os
import json
from datetime import datetime, timedelta
import google.generativeai as genai

# Configure Gemini (FREE tier - 60 requests/minute)
genai.configure(api_key=os.environ.get('GEMINI_API_KEY'))

def parse_natural_language_task(text):
    """
    Input: "Submit report by Friday 5pm urgent"
    Output: {
        'title': 'Submit report',
        'due_date': '2026-08-14T17:00:00',
        'priority': 'urgent',
        'category': 'Work'
    }
    """
    today = datetime.now().strftime('%Y-%m-%d')
    
    prompt = f"""Today is {today}. Parse this task into JSON:
    "{text}"
    
    Return ONLY valid JSON with these exact keys:
    - title (string)
    - due_date (ISO 8601 datetime string, or null if not specified)
    - priority (low/medium/high/urgent, default medium)
    - category (Work/Personal/Health/Finance/Shopping/Learning/Other)
    
    Example output: {{"title": "Submit report", "due_date": "2026-08-14T17:00:00", "priority": "urgent", "category": "Work"}}"""
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        
        # Clean the response (sometimes Gemini wraps JSON in markdown)
        raw_text = response.text.strip()
        if raw_text.startswith('```json'):
            raw_text = raw_text[7:]
        if raw_text.endswith('```'):
            raw_text = raw_text[:-3]
        
        result = json.loads(raw_text.strip())
        return result
    except Exception as e:
        print(f"AI parse failed: {e}")
        return {'title': text, 'due_date': None, 'priority': 'medium', 'category': 'Other'}


def suggest_category(task_title, task_description=''):
    categories = ['Work', 'Personal', 'Health', 'Finance', 'Shopping', 'Learning', 'Other']
    
    prompt = f"""Task: "{task_title}"
    Description: "{task_description}"
    
    Which category fits best? Choose ONLY from: {', '.join(categories)}.
    Return just the category name, nothing else."""
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        return response.text.strip()
    except:
        return 'Personal'


def generate_productivity_insight(user_stats):
    """user_stats is a dict with total, completed, overdue, etc."""
    
    prompt = f"""As a productivity coach, analyze this data:
    - Total tasks: {user_stats.get('total', 0)}
    - Completed: {user_stats.get('completed', 0)}
    - Overdue: {user_stats.get('overdue', 0)}
    
    Give ONE short, actionable tip (2 sentences max). Be encouraging."""
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        return response.text.strip()
    except:
        return "Break large tasks into smaller steps for better focus."


def generate_subtasks(task_title, task_description=''):
    prompt = f"""Break this task into 3-5 specific subtasks:
    Task: "{task_title}"
    Description: "{task_description}"
    
    Return ONLY a JSON array of strings. Example: ["Research topic", "Write outline", "Review draft"]"""
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        
        raw_text = response.text.strip()
        if raw_text.startswith('```json'):
            raw_text = raw_text[7:]
        if raw_text.endswith('```'):
            raw_text = raw_text[:-3]
            
        return json.loads(raw_text.strip())
    except:
        return []