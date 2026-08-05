document.addEventListener('DOMContentLoaded', function() {
    // Mobile menu toggle
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

    // Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            alert.style.transform = 'translateY(-10px)';
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    });

    // Animate progress bars on load
    const progressBars = document.querySelectorAll('.progress-bar-fill');
    progressBars.forEach(bar => {
        const width = bar.style.width;
        bar.style.width = '0';
        setTimeout(() => {
            bar.style.width = width;
        }, 200);
    });

    // Animate stat cards on scroll
    const statCards = document.querySelectorAll('.stat-card');
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
});

// Toggle task status (AJAX)
function toggleTaskStatus(btn) {
    const taskId = btn.dataset.taskId;
    const csrftoken = getCookie('csrftoken');

    fetch(`/tasks/${taskId}/toggle/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrftoken,
            'Content-Type': 'application/json',
        },
    })
    .then(response => response.json())
    .then(data => {
        const icon = btn.querySelector('i');
        const text = btn.querySelector('span');

        if (data.status === 'completed') {
            btn.classList.add('completed');
            icon.className = 'fas fa-check-circle';
            text.textContent = 'Completed';
            // Add completion animation
            btn.style.animation = 'pulse 0.5s ease';
            setTimeout(() => btn.style.animation = '', 500);
        } else {
            btn.classList.remove('completed');
            icon.className = 'fas fa-circle';
            text.textContent = 'Mark Done';
        }
    })
    .catch(error => console.error('Error:', error));
}

// Dropdown toggle
function toggleDropdown(btn) {
    const dropdown = btn.nextElementSibling;
    const isOpen = dropdown.classList.contains('show');

    // Close all dropdowns
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

// Add subtask
function addSubtask(taskId) {
    const input = document.getElementById('newSubtaskInput');
    const title = input.value.trim();
    if (!title) return;

    const csrftoken = getCookie('csrftoken');

    fetch(`/tasks/${taskId}/subtask/create/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrftoken,
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: `title=${encodeURIComponent(title)}`,
    })
    .then(response => response.json())
    .then(data => {
        if (data.id) {
            const list = document.getElementById('subtasksList');
            const item = document.createElement('div');
            item.className = 'subtask-item';
            item.dataset.id = data.id;
            item.innerHTML = `
                <span class="subtask-title">${data.title}</span>
                <button type="button" class="btn-icon" onclick="deleteSubtask(${data.id})">
                    <i class="fas fa-times"></i>
                </button>
            `;
            list.appendChild(item);
            input.value = '';
        }
    })
    .catch(error => console.error('Error:', error));
}

// Delete subtask
function deleteSubtask(subtaskId) {
    const csrftoken = getCookie('csrftoken');

    fetch(`/subtasks/${subtaskId}/delete/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrftoken,
            'Content-Type': 'application/json',
        },
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const item = document.querySelector(`.subtask-item[data-id="${subtaskId}"]`);
            if (item) {
                item.style.opacity = '0';
                item.style.transform = 'translateX(-20px)';
                setTimeout(() => item.remove(), 300);
            }
        }
    })
    .catch(error => console.error('Error:', error));
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
