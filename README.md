# ⚡ TaskFlow — AI-Powered Productivity & Task Management Suite

[![Django](https://img.shields.io/badge/Django-5.0-092E20?style=for-the-badge&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Celery](https://img.shields.io/badge/Celery-5.3-37814A?style=for-the-badge&logo=celery&logoColor=white)](https://docs.celeryq.dev/)
[![Redis](https://img.shields.io/badge/Redis-7.0-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Google Gemini](https://img.shields.io/badge/Google_Gemini-1.5_Flash-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

**TaskFlow** is an enterprise-grade, full-stack productivity suite engineered with Django 5, Celery, and Google Gemini AI. Designed for high-velocity workflows, it bridges generative AI with deterministic task execution — offering natural language task breakdown, interactive drag-and-drop calendar orchestration, RFC-5545 iCal synchronization, asynchronous background automation, dual-channel push alerts, and an offline-capable Progressive Web Application (PWA).

---

## 🏛️ System Architecture

```mermaid
graph TD
    subgraph Client["Client Tier (PWA & Desktop)"]
        UI["Web UI / FullCalendar.js"]
        SW["Service Worker (taskflow-v3)"]
        PushRec["Push Notification Listener"]
        UI <--> SW
    end

    subgraph Server["Application Tier (Gunicorn / Django 5)"]
        WSGI["Gunicorn WSGI Server"]
        Router["URL Dispatcher & Auth Middleware"]
        RL["Zero-Dependency Rate Limiter (tasks/ratelimit.py)"]
        Views["Task, Calendar & Analytics Views"]
        ORM["Django ORM (select_related / prefetch_related)"]

        WSGI --> Router
        Router --> RL
        RL --> Views
        Views --> ORM
    end

    subgraph Data["Data & Cache Tier"]
        DB[(PostgreSQL 15 / Connection Pool)]
        Redis[(Redis 7: Broker, Cache & Rate Limiting)]
    end

    subgraph AsyncTier["Async Automation Tier"]
        Beat["Celery Beat (Periodic Scheduler)"]
        Worker["Celery Worker Processes"]
        PushSender["pywebpush (VAPID) & SMTP Gateway"]

        Beat -->|Dispatch Tasks| Redis
        Redis -->|Consume Tasks| Worker
        Worker --> PushSender
    end

    subgraph External["External Services"]
        Gemini["Google Gemini 1.5 Flash API"]
        ExtCal["External Calendars (Google / Apple / Outlook)"]
    end

    SW <-->|HTTP / AJAX & CSRF| WSGI
    PushSender -->|Web Push Protocol| PushRec
    Views <-->|JSON NLP & Breakdown| Gemini
    Views -->|RFC-5545 Feed (.ics)| ExtCal
    ORM <-->|conn_max_age=600| DB
    Views <-->|Cache & Session Storage| Redis
    Worker <-->|State Updates| DB
```

---

## 🚀 Key Engineering Highlights

### 1. 🤖 AI Productivity Companion ("Nova")
- **Natural Language Parsing:** Automatically converts unstructured natural language inputs (e.g., *"Finish Q3 financial audit with Sarah by Friday 4pm urgent"*) into strongly typed database records with extracted titles, priorities, categories, and ISO timestamps.
- **Dynamic Subtask Breakdown:** Uses Gemini 1.5 Flash to generate atomic, actionable checklists for complex deliverables.
- **Defensive API Resilience:** Employs lazy SDK initialization to ensure zero boot overhead, regex-based markdown fence stripping for malformed LLM responses, and automatic fallback parsing to guarantee 100% uptime even during upstream API degradation.
- **Quota Protection:** Enforces sliding-window cache rate-limiting (`10 requests / 60 seconds` per user) preventing API abuse and quota exhaustion.

### 2. 📅 Interactive Scheduling & Calendar Synchronization
- **FullCalendar.js Orchestration:** Interactive monthly, weekly, and daily views supporting drag-and-drop rescheduling that persists via asynchronous JSON endpoints (`/api/tasks/<id>/reschedule/`).
- **RFC-5545 iCal Feed (`/tasks/export/ics/`):** Generates compliant VCALENDAR/VEVENT feeds allowing seamless live two-way subscription sync into Apple Calendar, Google Calendar, and Microsoft Outlook.

### 3. ⚙️ Asynchronous Task Queue & Automation
- **Celery & Redis Architecture:** Background tasks run asynchronously decoupled from the HTTP request-response cycle.
- **Recurrence Engine:** Automatic recurring task execution (Daily, Weekly, Monthly) via `tasks.process_recurring_tasks`.
- **Dual-Channel Reminders:** Sends time-critical task alerts via both VAPID Web Push (`pywebpush`) directly to the user's browser/mobile lock screen and SMTP email.
- **Nightly Telemetry & Analytics:** Celery Beat aggregates daily completed vs. pending tasks into `DailyAnalytics` tables at midnight UTC for performant dashboard metrics.

### 4. 📱 PWA & Offline Support
- **`taskflow-v3` Service Worker:** Implements a dual-tier caching strategy — **Cache-First** with background stale-while-revalidate for static assets (CSS, JS, fonts, icons) and **Network-First** with offline fallbacks for dynamic task routes.
- **W3C Manifest:** Complete manifest specification enabling full standalone installation on iOS, Android, macOS, and Windows.

### 5. 🛡️ Enterprise Security & Performance Hardening
- **Multi-Tenant IDOR Prevention:** Strict multi-tenant isolation where every database query, lookup, and mutation is hard-scoped to `user=request.user`. Authenticated attackers receive 404/403 upon attempting to access or manipulate foreign tasks, categories, or subtasks.
- **Sliding-Window Cache Rate Limiting:** Built-in zero-dependency rate limiter (`tasks/ratelimit.py`) guarding sensitive endpoints against brute-force attacks (`auth_login`: 5 attempts/min; `auth_signup`: 5 attempts/5 mins; `ai_task_create`: 10 requests/min).
- **N+1 Query Elimination:** Optimized queries utilizing `select_related('category')` and `prefetch_related('subtasks')`, slashing SQL query volume by over 80% on dashboard and list views.
- **Connection Pooling:** Configured with `dj-database-url` and `conn_max_age=600` for persistent database connection recycling under high concurrency.
- **Production Headers:** Enforces HSTS (31536000s), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `SECURE_PROXY_SSL_HEADER`, and secure cookie flags.

---

## 💻 Tech Stack

| Layer | Technologies |
| :--- | :--- |
| **Backend Framework** | **Django 5.0** (Python 3.11), Gunicorn WSGI |
| **Database & Cache** | **PostgreSQL 15**, **Redis 7** (In-Memory Cache & Session Store) |
| **Asynchronous & Queues**| **Celery 5.3**, **Celery Beat**, Redis Broker |
| **AI Integration** | **Google Gemini 1.5 Flash API** (`google-generativeai`) |
| **Frontend & Calendar** | HTML5, Vanilla JavaScript, **FullCalendar.js 6.1**, FontAwesome 6 |
| **PWA & Notifications** | W3C Service Worker (`taskflow-v3`), Web Push API (**VAPID / pywebpush**) |
| **DevOps & Infrastructure**| **Docker**, **Render Blueprint** (`render.yaml`), **GitHub Actions CI/CD** |

---

## 🛠️ Local Development Setup

### Prerequisites
- Python 3.11+
- Redis Server (local or Docker: `docker run -p 6379:6379 redis:7-alpine`)
- PostgreSQL (optional; defaults to SQLite for local development)

### 1. Clone Repository & Setup Virtual Environment
```bash
git clone https://github.com/akinola203/Todo-App.git
cd Todo-App

# Create and activate virtual environment
python -m venv .venv

# On Linux / macOS:
source .venv/bin/activate
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env` and populate your development keys:
```bash
cp .env.example .env
```

### 4. Run Database Migrations
```bash
python manage.py migrate
python manage.py collectstatic --noinput
```

### 5. Create Superuser (Optional)
```bash
python manage.py createsuperuser
```

### 6. Start Development Servers
**Terminal 1 — Django Web Application:**
```bash
python manage.py runserver
```

**Terminal 2 — Celery Worker & Beat:**
```bash
# On Linux / macOS:
celery -A todo_desktop worker --beat --loglevel=info

# On Windows (using solo execution pool):
celery -A todo_desktop worker --beat --loglevel=info --pool=solo
```

The application will be live at `http://127.0.0.1:8000/`.

---

## 🧪 Testing & Verification

TaskFlow includes a comprehensive test suite validating model integrity, asynchronous tasks, AI utilities, rate limiting, and multi-tenant IDOR isolation:

```bash
# Run system configuration checks
python manage.py check

# Run the full test suite (26 tests)
python manage.py test -v 2

# Run security & IDOR isolation test suite specifically
python manage.py test tasks.tests.TaskSecurityTestCase -v 2
```

---

## 🌐 Production Deployment

TaskFlow is configured for automated cloud deployment via **Render Blueprint** (`render.yaml`) and **GitHub Actions**:

### Render Blueprint Infrastructure
When linked to Render, `render.yaml` automatically provisions:
1. `taskflow` — Web application service running Gunicorn with `/ht/` health checking.
2. `taskflow-worker` — Dedicated background Celery worker + Celery Beat scheduler.
3. `taskflow-db` — Managed PostgreSQL 15 database instance.
4. `taskflow-redis` — Managed Redis instance for Celery brokering and distributed rate-limiting.

### GitHub Actions CI/CD Pipeline
Every push to `main` executes `.github/workflows/ci.yml`:
- Spins up Python 3.11 with Redis service container.
- Installs and caches dependencies.
- Runs Django system health checks and full test suite with coverage verification.

---

## 👤 Author

**Akinola**
- GitHub: [@akinola203](https://github.com/akinola203)
- Email: [akinakinlade777@gmail.com](mailto:akinakinlade777@gmail.com)
- Project Repository: [https://github.com/akinola203/Todo-App](https://github.com/akinola203/Todo-App)

---

*Licensed under the [MIT License](LICENSE).*

