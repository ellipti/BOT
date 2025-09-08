// Dashboard JavaScript utilities

// Auto-refresh configuration
let refreshInterval;
let isVisible = true;

// Initialize dashboard functionality
document.addEventListener("DOMContentLoaded", function () {
  setupAutoRefresh();
  setupVisibilityHandling();
  setupErrorHandling();
});

// Setup auto-refresh for live data
function setupAutoRefresh(intervalMs = 30000) {
  clearInterval(refreshInterval);

  refreshInterval = setInterval(() => {
    if (isVisible && document.visibilityState === "visible") {
      refreshDashboardData();
    }
  }, intervalMs);
}

// Handle page visibility changes
function setupVisibilityHandling() {
  document.addEventListener("visibilitychange", function () {
    isVisible = !document.hidden;

    if (isVisible) {
      // Page became visible, refresh immediately
      refreshDashboardData();
    }
  });
}

// Setup global error handling
function setupErrorHandling() {
  window.addEventListener("error", function (e) {
    console.error("Dashboard error:", e.error);
    showNotification("An error occurred. Please refresh the page.", "error");
  });
}

// Refresh dashboard data using HTMX or fetch
function refreshDashboardData() {
  // If HTMX is available, trigger refresh
  if (typeof htmx !== "undefined") {
    const refreshElements = document.querySelectorAll("[hx-get]");
    refreshElements.forEach((el) => {
      htmx.trigger(el, "refresh");
    });
  } else {
    // Fallback to page reload
    location.reload();
  }
}

// Show notification to user
function showNotification(message, type = "info") {
  // Create notification element
  const notification = document.createElement("div");
  notification.className = `notification notification-${type}`;
  notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 1rem 1.5rem;
        border-radius: 0.5rem;
        color: white;
        z-index: 9999;
        max-width: 400px;
        animation: slideIn 0.3s ease-out;
    `;

  // Set background color based on type
  const colors = {
    info: "#3182ce",
    success: "#38a169",
    warning: "#d69e2e",
    error: "#e53e3e",
  };
  notification.style.backgroundColor = colors[type] || colors.info;

  notification.textContent = message;

  // Add close button
  const closeBtn = document.createElement("button");
  closeBtn.innerHTML = "×";
  closeBtn.style.cssText = `
        background: none;
        border: none;
        color: white;
        font-size: 1.5rem;
        cursor: pointer;
        float: right;
        margin-left: 1rem;
        margin-top: -0.25rem;
    `;
  closeBtn.onclick = () => notification.remove();

  notification.appendChild(closeBtn);
  document.body.appendChild(notification);

  // Auto-remove after 5 seconds
  setTimeout(() => {
    if (notification.parentNode) {
      notification.remove();
    }
  }, 5000);
}

// Format numbers for display
function formatNumber(num, decimals = 2) {
  if (typeof num !== "number") return num;
  return num.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

// Format currency values
function formatCurrency(value, currency = "USD") {
  if (typeof value !== "number") return value;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currency,
    minimumFractionDigits: 2,
  }).format(value);
}

// Format timestamps
function formatTimestamp(timestamp) {
  if (!timestamp) return "";
  const date = new Date(timestamp);
  return date.toLocaleString();
}

// Utility function to debounce API calls
function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

// Add CSS animation for notifications
const style = document.createElement("style");
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
`;
document.head.appendChild(style);

// Export functions for global use
window.DashboardUtils = {
  refreshData: refreshDashboardData,
  showNotification,
  formatNumber,
  formatCurrency,
  formatTimestamp,
  debounce,
};
