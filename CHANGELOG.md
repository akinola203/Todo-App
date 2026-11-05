# Changelog

All notable changes to the TaskFlow project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.0.0] - 2026-11-05

### 🚀 TaskFlow v2.0.0 — Production Hardening, Scheduling Suite & PWA Upgrade

This release transforms TaskFlow into a production-ready, multi-tenant Progressive Web Application with enterprise security controls, asynchronous background workers, interactive calendar scheduling, and hardened AI pipelines.

### 🔒 Security & Performance Engineering
* **Environment & Credential Hardening:** Removed legacy hardcoded admin migrations and wired `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, and `CSRF_TRUSTED_ORIGINS` dynamically via environment variables.
* **Zero-Dependency Rate Limiting:** Added cache-backed rate limiting (`tasks/ratelimit.py`) to block brute-force login attempts (`5 req/min`) and protect Google Gemini API quotas (`10 req/min`).
* **Database Optimization:** Enabled persistent connection pooling (`conn_max_age=600`, `conn_health_checks=True`) via `dj-database-url` and eliminated N+1 queries across dashboard, task list, and calendar views using `.select_related()` and `.prefetch_related()`.
* **Multi-Tenant IDOR Test Suite:** Added comprehensive unit and security tests verifying strict `request.user` isolation across all views, AJAX endpoints, and exports.

### 📅 Interactive Calendar & iCal Sync
* **FullCalendar.js UI:** Added Month, Week, and Day views (`/calendar/`) with drag-and-drop task rescheduling (`/tasks/<id>/reschedule/`) and priority color-coding.
* **iCal (`.ics`) Export:** Added `/tasks/export/ics/` to generate RFC-5545 calendar feeds compatible with Google Calendar, Apple Calendar, and Outlook.

### ⚙️ Asynchronous Automation & Web Push
* **Recurring Tasks Engine:** Added `daily`, `weekly`, and `monthly` recurrence intervals processed hourly via Celery Beat (`process_recurring_tasks`).
* **Dual-Channel Reminders:** Upgraded `check_and_send_reminders` to dispatch encrypted VAPID Web Push notifications (`pywebpush`) alongside SMTP email alerts.
* **PWA Offline Support (`taskflow-v3`):** Re-engineered `sw.js` to enforce Cache-First for `/static/` assets and Network-First for authenticated HTML routes, paired with full `manifest.json` install support.

### 🛠️ DevOps & CI/CD
* **GitHub Actions Pipeline (`.github/workflows/ci.yml`):** Automated test runner with PostgreSQL 15 and Redis 7 service containers plus Render deployment webhook triggers.
* **Render Blueprint (`render.yaml`):** Infrastructure-as-Code provisioning for Gunicorn web service, Celery worker + Beat, PostgreSQL, and Redis.
