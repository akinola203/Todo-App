// TaskFlow Main Application JS
let deferredInstallPrompt = null;

document.addEventListener('DOMContentLoaded', function() {
    // 1. Mobile menu toggle
    const menuToggle = document.getElementById('menuToggle');
    const sidebar = document.getElementById('sidebar');

    if (menuToggle && sidebar) {
        menuToggle.addEventListener('click', function() {
            sidebar.classList.toggle('open');
        });

        // Close sidebar when clicking outside on mobile
        document.addEventListener('click', function(e) {
            if (window.innerWidth <= 768 && !sidebar.contains(e.target) && !menuToggle.contains(e.target)) {
                sidebar.classList.remove('open');
            }
        });
    }

    // 2. Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            alert.style.transform = 'translateY(-10px)';
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    });

    // 3. Animate progress bars on load
    const progressBars = document.querySelectorAll('.progress-bar-fill');
    progressBars.forEach(bar => {
        const width = bar.style.width;
        bar.style.width = '0';
        setTimeout(() => {
            bar.style.width = width;
        }, 200);
    });

    // 4. Animate stat cards on scroll
    const statCards = document.querySelectorAll('.stat-card');
    if ('IntersectionObserver' in window) {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach((entry, index) => {
                if (entry.isIntersecting) {
                    setTimeout(() => {
                        entry.target.style.opacity = '1';
                        entry.target.style.transform = 'translateY(0)';
                    }, index * 100);
                }
            });
        }, { threshold: 0.1 });

        statCards.forEach(card => {
            card.style.opacity = '0';
            card.style.transform = 'translateY(20px)';
            card.style.transition = 'all 0.5s ease';
            observer.observe(card);
        });
    }

    // 5. PWA Install Prompt Handler
    window.addEventListener('beforeinstallprompt', (e) => {
        e.preventDefault();
        deferredInstallPrompt = e;
        const installBtn = document.getElementById('pwaInstallBtn');
        if (installBtn) {
            installBtn.style.display = 'flex';
            installBtn.addEventListener('click', async () => {
                if (deferredInstallPrompt) {
                    deferredInstallPrompt.prompt();
                    const { outcome } = await deferredInstallPrompt.userChoice;
                    if (outcome === 'accepted') {
                        installBtn.style.display = 'none';
                    }
                    deferredInstallPrompt = null;
                }
            });
        }
    });

    // 6. Push notification prompt check
    initPushNotificationBtn();
});

// Toggle task status (AJAX)
function toggleTaskStatus(btn) {
    const taskId = btn.dataset.taskId;
    if (!taskId) return;
    const csrftoken = getCookie('csrftoken');

    fetch(`/tasks/${taskId}/toggle/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrftoken,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        },
    })
    .then(response => {
        if (!response.ok) throw new Error('Network response was not ok');
        return response.json();
    })
    .then(data => {
        const icon = btn.querySelector('i');
        const text = btn.querySelector('span');

        if (data.status === 'completed') {
            btn.classList.add('completed');
            if (icon) icon.className = 'fas fa-check-circle';
            if (text) text.textContent = 'Completed';
            btn.style.animation = 'pulse 0.5s ease';
            setTimeout(() => btn.style.animation = '', 500);
        } else {
            btn.classList.remove('completed');
            if (icon) icon.className = 'fas fa-circle';
            if (text) text.textContent = 'Mark Done';
        }
    })
    .catch(error => console.error('Error toggling task:', error));
}

// Dropdown toggle
function toggleDropdown(btn) {
    const dropdown = btn.nextElementSibling;
    if (!dropdown) return;
    const isOpen = dropdown.classList.contains('show');

    // Close all other dropdowns
    document.querySelectorAll('.dropdown-menu').forEach(d => d.classList.remove('show'));

    if (!isOpen) {
        dropdown.classList.add('show');
    }

    // Close on outside click
    document.addEventListener('click', function closeDropdown(e) {
        if (!btn.contains(e.target) && !dropdown.contains(e.target)) {
            dropdown.classList.remove('show');
            document.removeEventListener('click', closeDropdown);
        }
    });
}

// Toggle subtask status (AJAX)
function toggleSubtaskStatus(checkbox, subtaskId) {
    const csrftoken = getCookie('csrftoken');
    const row = checkbox.closest('.subtask-row') || checkbox.closest('.subtask-item');

    fetch(`/subtasks/${subtaskId}/toggle/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrftoken,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        },
    })
    .then(response => {
        if (!response.ok) throw new Error('Subtask toggle failed');
        return response.json();
    })
    .then(data => {
        if (row) {
            if (data.is_completed) {
                row.classList.add('completed-row');
            } else {
                row.classList.remove('completed-row');
            }
        }
    })
    .catch(error => {
        console.error('Error toggling subtask:', error);
        checkbox.checked = !checkbox.checked;
    });
}

// Add subtask (AJAX)
function addSubtask(taskId) {
    const input = document.getElementById('newSubtaskInput');
    if (!input) return;
    const title = input.value.trim();
    if (!title) return;

    const csrftoken = getCookie('csrftoken');

    fetch(`/tasks/${taskId}/subtask/create/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrftoken,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        },
        body: JSON.stringify({ title: title }),
    })
    .then(response => {
        if (!response.ok) throw new Error('Subtask creation failed');
        return response.json();
    })
    .then(data => {
        if (data.id) {
            const list = document.getElementById('subtasksList');
            if (list) {
                const item = document.createElement('div');
                item.className = 'subtask-row';
                item.dataset.id = data.id;
                item.innerHTML = `
                    <span class="drag-handle-grip"><i class="fas fa-grip-vertical"></i></span>
                    <label class="shakuro-circular-checkbox">
                        <input type="checkbox" onchange="toggleSubtaskStatus(this, ${data.id})">
                        <span class="circle-check-indicator"></span>
                    </label>
                    <div class="subtask-details">
                        <span class="subtask-text">${escapeHtml(data.title)}</span>
                        <span class="subtask-parent-ref">Recently added</span>
                    </div>
                    <button type="button" class="btn-subtask-del" onclick="deleteSubtask(${data.id})">
                        <i class="fas fa-times"></i>
                    </button>
                `;
                list.prepend(item);
            }
            input.value = '';
        }
    })
    .catch(error => console.error('Error adding subtask:', error));
}

// Delete subtask (AJAX)
function deleteSubtask(subtaskId) {
    const csrftoken = getCookie('csrftoken');

    fetch(`/subtasks/${subtaskId}/delete/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrftoken,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        },
    })
    .then(response => {
        if (!response.ok) throw new Error('Subtask deletion failed');
        return response.json();
    })
    .then(data => {
        if (data.success) {
            const item = document.querySelector(`.subtask-row[data-id="${subtaskId}"], .subtask-item[data-id="${subtaskId}"]`);
            if (item) {
                item.style.opacity = '0';
                item.style.transform = 'translateX(-20px)';
                setTimeout(() => item.remove(), 300);
            }
        }
    })
    .catch(error => console.error('Error deleting subtask:', error));
}

// Web Push Notification setup
function initPushNotificationBtn() {
    const pushBtn = document.getElementById('enablePushBtn');
    if (!pushBtn) return;

    if (!('Notification' in window) || !('serviceWorker' in navigator)) {
        pushBtn.style.display = 'none';
        return;
    }

    if (Notification.permission === 'granted') {
        pushBtn.innerHTML = '<i class="fas fa-bell"></i> Push Enabled';
        pushBtn.disabled = true;
        pushBtn.classList.add('btn-ghost');
    } else {
        pushBtn.addEventListener('click', subscribeUserToPush);
    }
}

async function subscribeUserToPush() {
    try {
        const permission = await Notification.requestPermission();
        if (permission !== 'granted') {
            alert('Push notifications permission was denied.');
            return;
        }

        const registration = await navigator.serviceWorker.ready;
        const keyResponse = await fetch('/api/push/vapid-key/');
        const { publicKey } = await keyResponse.json();

        if (!publicKey) {
            console.warn('VAPID public key not configured on server.');
            return;
        }

        const applicationServerKey = urlB64ToUint8Array(publicKey);
        const subscription = await registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: applicationServerKey
        });

        const csrftoken = getCookie('csrftoken');
        const saveResponse = await fetch('/api/push/subscribe/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrftoken,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(subscription)
        });

        if (saveResponse.ok) {
            const pushBtn = document.getElementById('enablePushBtn');
            if (pushBtn) {
                pushBtn.innerHTML = '<i class="fas fa-bell"></i> Push Enabled';
                pushBtn.disabled = true;
            }
        }
    } catch (error) {
        console.error('Failed to subscribe user to push:', error);
    }
}

function urlB64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding).replace(/\-/g, '+').replace(/_/g, '/');
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
}

// CSRF token helper
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function escapeHtml(str) {
    return String(str || '')
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
