import { createPlayerCardComponent, createLeagueElement } from './components.js';
import { fetchPlayerStatus, fetchTopPlayers, fetchPlayerDetails, searchPlayers } from './api.js';

// Estado da UI
const appState = { expandedState: {} };
const POSITIONS = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF', 'DL', 'LB', 'DB'];
const STATUS_ORDER = { 'PUP': 0, 'IR': 1, 'Suspended': 2, 'OUT': 3, 'Doubtful': 4, 'Questionable': 5, 'Probable': 6 };

// --- Aba "Status Player" ---
export async function loadPlayerStatus(forceRefresh = false, showBestBall = false) {
    const container = document.getElementById('leagues-container');
    const noIssues = document.getElementById('no-issues-message');
    const reloadBtn = document.getElementById('reload-btn');
    
    reloadBtn.disabled = true;
    reloadBtn.textContent = "Loading...";
    container.innerHTML = '<div class="loading">Loading player status...</div>';
    
    try {
        const leagues = await fetchPlayerStatus(forceRefresh, showBestBall);
        noIssues.style.display = Object.keys(leagues).length === 0 ? 'block' : 'none';
        container.innerHTML = '';
        
        Object.entries(leagues).forEach(([leagueId, league]) => {
            league.issues.sort((a, b) => (STATUS_ORDER[a.status] ?? 99) - (STATUS_ORDER[b.status] ?? 99));
            const leagueEl = createLeagueElement(leagueId, league, appState.expandedState);
            container.appendChild(leagueEl);
            addLeagueEventListeners(leagueEl);
        });
    } catch (error) {
        container.innerHTML = `<div class="error"><p>Error loading player status:</p><p><strong>${error.message}</strong></p></div>`;
    } finally {
        reloadBtn.disabled = false;
        reloadBtn.textContent = "↻ Reload";
    }
}

function addLeagueEventListeners(leagueEl) {
    const leagueId = leagueEl.dataset.leagueId;
    leagueEl.querySelector('.league-header').addEventListener('click', () => toggleLeague(leagueId, leagueEl));
    leagueEl.querySelectorAll('.group-header').forEach(header => {
        header.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleStatusGroup(leagueId, header);
        });
    });
}

function toggleLeague(leagueId, leagueEl) {
    const header = leagueEl.querySelector('.league-header');
    const content = leagueEl.querySelector('.league-content');
    const isExpanded = !(header.dataset.expanded === 'true');
    
    appState.expandedState[leagueId] = { ...appState.expandedState[leagueId], expanded: isExpanded };
    header.dataset.expanded = isExpanded;
    content.style.display = isExpanded ? 'block' : 'none';
    header.querySelector('.toggle-icon').textContent = isExpanded ? '▲' : '▼';
}

function toggleStatusGroup(leagueId, groupHeader) {
    const content = groupHeader.nextElementSibling;
    const status = groupHeader.dataset.status;
    const isExpanded = !(groupHeader.dataset.expanded === 'true');
    
    appState.expandedState[leagueId] = appState.expandedState[leagueId] || { statuses: {} };
    appState.expandedState[leagueId].statuses = { ...appState.expandedState[leagueId].statuses, [status]: isExpanded };

    groupHeader.dataset.expanded = isExpanded;
    content.style.display = isExpanded ? 'block' : 'none';
    groupHeader.querySelector('.toggle-icon').textContent = isExpanded ? '▲' : '▼';
}

// --- Aba "Find Player" ---
export function initFindForPlayerTab() {
    loadTopPlayers();
    initPositionFilters();
}

async function loadTopPlayers() {
    const container = document.getElementById('top-players-container');
    container.innerHTML = '<div class="loading">Loading your top players...</div>';
    try {
        const players = await fetchTopPlayers();
        container.innerHTML = '';
        if (players.length === 0) {
            container.innerHTML = '<div class="no-players">No players found</div>';
            return;
        }
        players.forEach(player => {
            const card = createPlayerCardComponent({
                playerName: player.name, leagues: player.leagues,
                position: player.position, injuryStatus: player.injury_status
            });
            container.appendChild(card);
        });
    } catch (error) {
        container.innerHTML = `<div class="error"><p>Error: ${error.message}</p></div>`;
    }
}

function initPositionFilters() {
    const container = document.getElementById('positions-container');
    container.innerHTML = POSITIONS.map(pos => `
        <label class="position-filter">
            <input type="checkbox" name="position" value="${pos}" checked> ${pos}
        </label>
    `).join('');
    container.addEventListener('change', updateSearchSuggestions);
}

export const updateSearchSuggestions = debounce(async () => {
    const input = document.getElementById('player-search-input');
    const suggestionsEl = document.getElementById('search-suggestions');
    const query = input.value.trim();
    
    if (query.length < 3) {
        suggestionsEl.style.display = 'none';
        return;
    }

    try {
        const positions = Array.from(document.querySelectorAll('.position-filter input:checked')).map(cb => cb.value);
        const players = await searchPlayers(query, positions);
        
        suggestionsEl.innerHTML = '';
        if (players.length === 0) {
            suggestionsEl.innerHTML = '<div class="no-results">No players match</div>';
        } else {
            players.forEach(player => {
                const div = document.createElement('div');
                div.className = 'suggestion-item';
                div.innerHTML = `<strong>${player.name}</strong> <span>${player.positions.join(', ')}</span>`;
                div.onclick = () => {
                    input.value = player.name;
                    suggestionsEl.style.display = 'none';
                    showPlayerSearchResults(player);
                };
                suggestionsEl.appendChild(div);
            });
        }
        suggestionsEl.style.display = 'block';
    } catch (error) {
        suggestionsEl.innerHTML = '<div class="no-results">Search unavailable</div>';
        suggestionsEl.style.display = 'block';
    }
}, 300);

async function showPlayerSearchResults(player) {
    const resultsContainer = document.getElementById('search-results');
    resultsContainer.innerHTML = '<div class="loading">Searching player...</div>';
    try {
        const data = await fetchPlayerDetails(player.name);
        
         // Verificar se temos dados válidos
        if (!data || data.error) {
            resultsContainer.innerHTML = `<div class="no-results">${player.name} not found or error: ${data?.error || 'Unknown error'}</div>`;
            return;
        }
        // Criar o card do jogador com os dados corretos
        const cardData = {
            playerName: player.name,
            leagues: data.leagues,
            position: data.position || '?',
            injuryStatus: data.injury_status || 'Active'
        };

        const card = createPlayerCardComponent(cardData);
        resultsContainer.innerHTML = '';
        resultsContainer.appendChild(card);

    } catch (error) {
        resultsContainer.innerHTML = `<div class="error"><p>Error: ${error.message}</p></div>`;
    }
}

// --- Funções Auxiliares ---
function debounce(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}