// ================= STATE =================
const API_BASE = "http://127.0.0.1:5000";

let currentRequests = [];
let currentVolunteers = [];
let currentMatches = [];

// ================= INIT =================
document.addEventListener('DOMContentLoaded', () => {
    loadRequests();
});

// ================= LOAD =================
async function loadRequests() {
    try {
        showLoading("Loading requests...");
        currentRequests = await safeFetch(`${API_BASE}/api/requests`);
        displayRequests(currentRequests);
    } finally {
        hideLoading();
    }
}

async function loadVolunteers() {
    try {
        showLoading("Loading volunteers...");
        currentVolunteers = await safeFetch(`${API_BASE}/api/volunteers`);
        displayVolunteers(currentVolunteers);
    } finally {
        hideLoading();
    }
}

async function loadMatches() {
    try {
        showLoading("Loading matches...");
        currentMatches = await safeFetch(`${API_BASE}/api/matches`);
        displayMatches(currentMatches);
    } finally {
        hideLoading();
    }
}

// ================= DISPLAY =================
function displayRequests(requests) {
    const container = document.getElementById('requestsList');
    if (!container) return;

    container.innerHTML = '';

    if (!requests.length) {
        container.innerHTML = "<p>No requests</p>";
        return;
    }

    requests.forEach(r => {
        container.innerHTML += `
        <div class="col-md-4">
            <div class="card p-3 shadow-sm">
                <h6>${r.name || ''}</h6>
                <p>${r.description || ''}</p>
                <span class="badge bg-${getUrgencyColor(r.urgency)}">${r.urgency}</span>
                <button class="btn btn-sm btn-primary mt-2"
                    onclick="matchVolunteerAI('${r.id}')">
                    AI Match
                </button>
            </div>
        </div>`;
    });
}

function displayVolunteers(vols) {
    const container = document.getElementById('volunteersList');
    if (!container) return;

    container.innerHTML = '';

    vols.forEach(v => {
        container.innerHTML += `
        <div class="col-md-4">
            <div class="card p-3">
                <h6>${v.name}</h6>
                <p>${v.skills}</p>
            </div>
        </div>`;
    });
}

function displayMatches(matches) {
    const container = document.getElementById('matchesList');
    if (!container) return;

    container.innerHTML = '';

    matches.forEach(m => {
        container.innerHTML += `
        <div class="col-md-4">
            <div class="card p-3 border-warning">
                <h6>Request ${m.request_id}</h6>
                ${(m.matches || []).map(x => `
                    <div>
                        ${x.name}
                        <span class="badge bg-${getScoreColor(x.score || 0)}">
                            ${(x.score * 100).toFixed(0)}%
                        </span>
                    </div>
                `).join('')}
            </div>
        </div>`;
    });
}

// ================= AI MATCH =================
async function matchVolunteerAI(id) {
    try {
        showLoading("AI Matching...");

        await safeFetch(`${API_BASE}/api/match-volunteer`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ request_id: id })
        });

        showAlert('success', "Match created!");

        loadRequests();
        loadMatches();

    } catch (e) {
        showAlert('error', "Matching failed");
    } finally {
        hideLoading();
    }
}