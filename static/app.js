// Agent Hub Frontend JavaScript

// State
let allAgents = [];
let filteredAgents = [];
let currentPage = 1;
const pageSize = 6;
let filterMode = 'all'; // 'all' or 'mine'

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    // Only load agents if we're on the main page
    if (document.getElementById('agent-grid')) {
        loadAgents();
    }
});

// Get current username
function getCurrentUsername() {
    return document.querySelector('[data-username]')?.dataset.username || '';
}

// Load and display agents
async function loadAgents() {
    const loading = document.getElementById('loading');
    const emptyState = document.getElementById('empty-state');
    const agentGrid = document.getElementById('agent-grid');

    try {
        const response = await fetch('/api/agents', { credentials: 'same-origin' });
        if (!response.ok) throw new Error('Failed to load agents');

        allAgents = await response.json();
        applyFilter();

        loading.classList.add('hidden');

        if (filteredAgents.length === 0) {
            emptyState.classList.remove('hidden');
            agentGrid.classList.add('hidden');
            document.getElementById('pagination')?.classList.add('hidden');
        } else {
            emptyState.classList.add('hidden');
            agentGrid.classList.remove('hidden');
            renderAgents();
        }
    } catch (error) {
        loading.innerHTML = `
            <div class="text-red-600">
                <p>Failed to load agents</p>
                <button onclick="loadAgents()" class="mt-2 text-indigo-600 hover:underline">Retry</button>
            </div>
        `;
    }
}

// Apply filter
function applyFilter() {
    const username = getCurrentUsername();
    if (filterMode === 'mine') {
        filteredAgents = allAgents.filter(a => a.registered_by === username);
    } else {
        filteredAgents = [...allAgents];
    }
    currentPage = 1;
}

// Toggle filter
function toggleFilter() {
    filterMode = filterMode === 'all' ? 'mine' : 'all';
    document.getElementById('filter-label').textContent = filterMode === 'all' ? 'All' : 'Mine';
    document.getElementById('filter-btn').classList.toggle('bg-indigo-100', filterMode === 'mine');
    applyFilter();

    const emptyState = document.getElementById('empty-state');
    const agentGrid = document.getElementById('agent-grid');

    if (filteredAgents.length === 0) {
        emptyState.classList.remove('hidden');
        agentGrid.classList.add('hidden');
        document.getElementById('pagination')?.classList.add('hidden');
    } else {
        emptyState.classList.add('hidden');
        agentGrid.classList.remove('hidden');
        renderAgents();
    }
}

// Render agent cards with pagination
function renderAgents() {
    const grid = document.getElementById('agent-grid');
    const totalPages = Math.ceil(filteredAgents.length / pageSize);
    const start = (currentPage - 1) * pageSize;
    const end = start + pageSize;
    const pageAgents = filteredAgents.slice(start, end);

    grid.innerHTML = pageAgents.map(agent => createAgentCard(agent)).join('');

    // Update pagination
    updatePagination(totalPages);
}

// Update pagination UI
function updatePagination(totalPages) {
    const pagination = document.getElementById('pagination');
    const pageInfo = document.getElementById('page-info');
    const prevBtn = document.getElementById('prev-btn');
    const nextBtn = document.getElementById('next-btn');

    if (totalPages <= 1) {
        pagination.classList.add('hidden');
        return;
    }

    pagination.classList.remove('hidden');
    pageInfo.textContent = `${currentPage} / ${totalPages}`;
    prevBtn.disabled = currentPage === 1;
    nextBtn.disabled = currentPage === totalPages;
}

// Pagination controls
function prevPage() {
    if (currentPage > 1) {
        currentPage--;
        renderAgents();
    }
}

function nextPage() {
    const totalPages = Math.ceil(filteredAgents.length / pageSize);
    if (currentPage < totalPages) {
        currentPage++;
        renderAgents();
    }
}

// Create agent card HTML
function createAgentCard(agent) {
    const healthClass = agent.is_healthy ? 'bg-green-500 health-healthy' : 'bg-red-500 health-unhealthy';
    const healthText = agent.is_healthy ? 'Healthy' : 'Unhealthy';

    const skills = agent.skills || [];
    const skillsHtml = skills.slice(0, 3).map(skill =>
        `<span class="skill-badge">${escapeHtml(skill.name || skill.id || 'Unknown')}</span>`
    ).join('');
    const moreSkills = skills.length > 3 ? `<span class="text-xs text-gray-500">+${skills.length - 3} more</span>` : '';

    return `
        <div class="agent-card bg-white rounded-lg shadow-md overflow-hidden">
            <div class="p-6">
                <div class="flex justify-between items-start mb-4">
                    <div class="flex-1 min-w-0">
                        <h3 class="text-lg font-semibold text-gray-900 truncate">
                            ${escapeHtml(agent.name || 'Unnamed Agent')}
                        </h3>
                        <p class="text-sm text-gray-500">${escapeHtml(agent.version || 'No version')}</p>
                    </div>
                    <div class="flex items-center gap-2 ml-4">
                        <span class="w-3 h-3 rounded-full ${healthClass}"></span>
                        <span class="text-xs text-gray-500">${healthText}</span>
                    </div>
                </div>

                <p class="text-gray-600 text-sm truncate-2 mb-4 h-10">
                    ${escapeHtml(agent.description || 'No description available')}
                </p>

                ${skills.length > 0 ? `
                    <div class="mb-4">
                        <p class="text-xs text-gray-500 mb-2">Skills</p>
                        <div class="flex flex-wrap gap-1">
                            ${skillsHtml}
                            ${moreSkills}
                        </div>
                    </div>
                ` : ''}

                <div class="text-xs text-gray-500 mb-4">
                    <p>Registered by: <strong>${escapeHtml(agent.registered_by)}</strong></p>
                    <p>URL: <code class="bg-gray-100 px-1 rounded text-xs">${escapeHtml(agent.url)}</code></p>
                </div>

                <div class="flex gap-2">
                    <button
                        onclick="copyAgentUrl('${escapeHtml(agent.url)}')"
                        class="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50 transition"
                    >
                        Copy URL
                    </button>
                    <a
                        href="/playground?agent=${agent.id}"
                        class="flex-1 px-3 py-2 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700 transition text-center"
                    >
                        Test
                    </a>
                    <button
                        onclick="deleteAgent(${agent.id})"
                        class="px-3 py-2 text-sm text-red-600 border border-red-300 rounded-md hover:bg-red-50 transition"
                        title="Delete"
                    >
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                        </svg>
                    </button>
                </div>
            </div>
        </div>
    `;
}

// Register Modal
function openRegisterModal() {
    document.getElementById('register-modal').classList.remove('hidden');
    document.getElementById('agent-url').value = '';
    document.getElementById('register-error').classList.add('hidden');
}

function closeRegisterModal() {
    document.getElementById('register-modal').classList.add('hidden');
}

async function registerAgent() {
    const urlInput = document.getElementById('agent-url');
    const errorDiv = document.getElementById('register-error');
    const btn = document.getElementById('register-btn');

    const url = urlInput.value.trim();
    if (!url) {
        errorDiv.textContent = 'Please enter an agent URL';
        errorDiv.classList.remove('hidden');
        return;
    }

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner inline-block mr-2"></span>Registering...';
    errorDiv.classList.add('hidden');

    try {
        const response = await fetch('/api/agents', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url }),
            credentials: 'same-origin'
        });

        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.detail || 'Failed to register agent');
        }

        closeRegisterModal();
        showToast('Agent registered successfully!');
        loadAgents();
    } catch (error) {
        errorDiv.textContent = error.message;
        errorDiv.classList.remove('hidden');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Register';
    }
}

// Delete Agent
async function deleteAgent(agentId) {
    if (!confirm('Are you sure you want to delete this agent?')) {
        return;
    }

    try {
        const response = await fetch(`/api/agents/${agentId}`, {
            method: 'DELETE',
            credentials: 'same-origin'
        });

        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.detail || 'Failed to delete agent');
        }

        showToast('Agent deleted successfully');
        loadAgents();
    } catch (error) {
        alert(error.message);
    }
}

// Copy URL
function copyAgentUrl(url) {
    navigator.clipboard.writeText(url).then(() => {
        showToast('URL copied to clipboard!');
    }).catch(() => {
        // Fallback for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = url;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
        showToast('URL copied to clipboard!');
    });
}

// Toast notification
function showToast(message) {
    const toast = document.getElementById('toast');
    const toastMessage = document.getElementById('toast-message');

    toastMessage.textContent = message;
    toast.classList.remove('hidden');
    toast.classList.add('toast-enter');

    setTimeout(() => {
        toast.classList.remove('toast-enter');
        toast.classList.add('toast-exit');
        setTimeout(() => {
            toast.classList.add('hidden');
            toast.classList.remove('toast-exit');
        }, 300);
    }, 3000);
}

// Utility: Escape HTML
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Close modals on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeRegisterModal();
    }
});

// Close modals when clicking outside
document.getElementById('register-modal')?.addEventListener('click', (e) => {
    if (e.target.id === 'register-modal') closeRegisterModal();
});

