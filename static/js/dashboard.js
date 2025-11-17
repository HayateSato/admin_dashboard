// Privacy Umbrella Admin Dashboard JavaScript

// Auto-refresh dashboard every 30 seconds
const AUTO_REFRESH_INTERVAL = 30000;

// Fetch system stats
async function fetchSystemStats() {
    try {
        const response = await fetch('/api/monitoring/system-stats');
        const data = await response.json();
        updateSystemStats(data);
    } catch (error) {
        console.error('Failed to fetch system stats:', error);
    }
}

// Update system stats display
function updateSystemStats(data) {
    // Update CPU, memory, etc. if elements exist
    console.log('System stats:', data);
}

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    // Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });

    // Start auto-refresh if on dashboard page
    if (window.location.pathname === '/dashboard') {
        setInterval(fetchSystemStats, AUTO_REFRESH_INTERVAL);
    }
});

// Utility functions
function showLoading(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.innerHTML = '<div class="spinner"></div>';
    }
}

function showError(message) {
    alert(message);
}

function showSuccess(message) {
    alert(message);
}
