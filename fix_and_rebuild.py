
# Create a script that fixes analytics.html with explicit newlines
fix_script = r'''import os

analytics_content = "{% extends 'base.html' %}\n\n{% block title %}Analytics - TaskFlow{% endblock %}\n\n{% block page_title %}Analytics{% endblock %}\n\n{% block content %}\n<div class=\"analytics-page\">\n  <div class=\"stats-grid\">\n    <div class=\"stat-card glow-purple\">\n      <div class=\"stat-icon\"><i class=\"fas fa-clipboard-list\"></i></div>\n      <div class=\"stat-info\"><h3>{{ total_tasks }}</h3><p>Total Tasks</p></div>\n    </div>\n    <div class=\"stat-card glow-green\">\n      <div class=\"stat-icon\"><i class=\"fas fa-check-circle\"></i></div>\n      <div class=\"stat-info\"><h3>{{ completed_tasks }}</h3><p>Completed</p></div>\n    </div>\n    <div class=\"stat-card glow-blue\">\n      <div class=\"stat-icon\"><i class=\"fas fa-clock\"></i></div>\n      <div class=\"stat-info\"><h3>{{ pending_tasks }}</h3><p>Pending</p></div>\n    </div>\n    <div class=\"stat-card glow-yellow\">\n      <div class=\"stat-icon\"><i class=\"fas fa-calendar-check\"></i></div>\n      <div class=\"stat-info\"><h3>{{ monthly_completed }}</h3><p>This Month</p></div>\n    </div>\n  </div>\n\n  <div class=\"dashboard-grid\">\n    <div class=\"glass-card chart-card\">\n      <h3><i class=\"fas fa-chart-line\"></i> Weekly Activity</h3>\n      <div class=\"bar-chart\">\n        {% for day in week_data %}\n        <div class=\"bar-group\">\n          <div class=\"bar-stack\">\n            <div class=\"bar created\" style=\"height: {{ day.created|default:0 }}em; max-height: 120px;\"></div>\n            <div class=\"bar completed\" style=\"height: {{ day.completed|default:0 }}em; max-height: 120px;\"></div>\n          </div>\n          <span class=\"bar-label\">{{ day.date }}</span>\n        </div>\n        {% endfor %}\n      </div>\n      <div class=\"chart-legend\">\n        <span><span class=\"legend-dot created\"></span> Created</span>\n        <span><span class=\"legend-dot completed\"></span> Completed</span>\n      </div>\n    </div>\n\n    <div class=\"glass-card chart-card\">\n      <h3><i class=\"fas fa-chart-pie\"></i> Priority Breakdown</h3>\n      <div class=\"priority-bars\">\n        {% for p in priority_data %}\n        <div class=\"priority-row\">\n          <span class=\"priority-label\">{{ p.priority|title }}</span>\n          <div class=\"priority-track\">\n            <div class=\"priority-fill {{ p.priority }}\" style=\"width: {{ p.count }}%\"></div>\n          </div>\n          <span class=\"priority-count\">{{ p.count }}</span>\n        </div>\n        {% endfor %}\n      </div>\n    </div>\n  </div>\n\n  <div class=\"glass-card chart-card full-width\" style=\"margin-top: 20px\">\n    <h3><i class=\"fas fa-tags\"></i> Tasks by Category</h3>\n    <div class=\"category-chips\">\n      {% for cat in category_data %}\n      <div class=\"category-chip\" style=\"border-color: {{ cat.color }}; color: {{ cat.color }}\">\n        <span class=\"chip-name\">{{ cat.name }}</span>\n        <span class=\"chip-count\">{{ cat.count }}</span>\n      </div>\n      {% endfor %}\n    </div>\n  </div>\n</div>\n{% endblock %}\n"

filepath = os.path.join('templates', 'tasks', 'analytics.html')
with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
    f.write(analytics_content)

print("=" * 60)
print("FIXED: templates/tasks/analytics.html")
print("=" * 60)
print("\nNow you MUST rebuild the .exe. Run these commands:\n")
print("  rmdir /s /q build dist")
print("  del TaskFlow.spec")
print("  pyinstaller --onefile --name TaskFlow ^")
print("    --add-data \"templates;templates\" ^")
print("    --add-data \"static;static\" ^")
print("    --add-data \"todo_desktop;todo_desktop\" ^")
print("    --add-data \"tasks;tasks\" ^")
print("    --add-data \"db.sqlite3;.\" ^")
print("    run_app.py")
print("\nThen run: dist\\TaskFlow.exe")
'''

with open("/mnt/agents/output/fix_and_rebuild.py", "w", encoding="utf-8") as f:
    f.write(fix_script)

print("✅ fix_and_rebuild.py created")
