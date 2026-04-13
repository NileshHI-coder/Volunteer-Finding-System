// ================= GLOBAL SAFE STATE =================
window.AppUI = window.AppUI || {};
window.AppUI.loadingOverlay = null;
window.AppUI.alertTimeout = null;

// ================= LOADING =================
function showLoading(message = 'Processing...') {
    hideLoading();

    const overlay = document.createElement('div');
    overlay.className = 'loading-overlay';
    overlay.innerHTML = `
        <div style="text-align:center;">
            <div class="spinner-border text-primary mb-3"></div>
            <div class="fw-bold">${message}</div>
        </div>
    `;

    document.body.appendChild(overlay);
    window.AppUI.loadingOverlay = overlay;
}

function hideLoading() {
    if (window.AppUI.loadingOverlay) {
        window.AppUI.loadingOverlay.remove();
        window.AppUI.loadingOverlay = null;
    }
}

// ================= ALERTS =================
function showAlert(type, message, duration = 4000) {
    if (window.AppUI.alertTimeout) {
        clearTimeout(window.AppUI.alertTimeout);
    }

    const div = document.createElement('div');
    div.className = `alert alert-${type === 'error' ? 'danger' : type} position-fixed`;
    div.style = "top:20px; right:20px; z-index:9999; min-width:300px";

    div.innerHTML = `
        ${message}
        <button class="btn-close float-end" onclick="this.parentElement.remove()"></button>
    `;

    document.body.appendChild(div);

    window.AppUI.alertTimeout = setTimeout(() => div.remove(), duration);
}

// ================= HELPERS =================
function getUrgencyColor(u) {
    return {
        Low: 'success',
        Medium: 'warning',
        High: 'danger'
    }[u] || 'secondary';
}

function getScoreColor(score) {
    if (score >= 0.9) return 'success';
    if (score >= 0.7) return 'warning';
    return 'danger';
}

// ================= SAFE FETCH =================
async function safeFetch(url, options = {}) {
    try {
        const res = await fetch(url, options);

        if (!res.ok) {
            const text = await res.text();
            throw new Error(`HTTP ${res.status}: ${text}`);
        }

        return await res.json();
    } catch (err) {
        console.error(err);
        showAlert('error', err.message);
        throw err;
    }
}