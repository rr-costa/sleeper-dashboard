import { createPlayerCardComponent, createLeagueElement } from './components.js';
import { fetchPlayerStatus, fetchTopPlayers, fetchPlayerDetails, searchPlayers, fetchNflTeams, fetchDepthChart } from './api.js';

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

// --- Aba "Depth Chart" ---

const POSICAO_ORDEM = { 'QB': 1, 'RB': 2, 'WR': 3, 'TE': 4, 'DL': 5, 'LB': 6, 'DB': 7, 'K': 8 };

export async function initDepthChartTab() {
    const teamSelect = document.getElementById('select-nfl-team');
    
    // Só carrega os times se a lista estiver vazia
    if (teamSelect.options.length <= 1) {
        try {
            const teams = await fetchNflTeams();
            teams.forEach(team => {
                const option = new Option(team, team);
                teamSelect.add(option);
            });
        } catch (error) {
            console.error(error);
        }
    }
    
    // Adiciona as ligas do usuário ao select de contexto
    populateLeagueContextSelect();

    // Adiciona os event listeners
    const leagueSelect = document.getElementById('select-league-context');
    teamSelect.addEventListener('change', handleDepthChartSelection);
    leagueSelect.addEventListener('change', handleDepthChartSelection);
}

async function populateLeagueContextSelect() {
    const leagueSelect = document.getElementById('select-league-context');
    if (leagueSelect.options.length > 1) return; // Já populado
    
    try {
        // Usa a mesma API da primeira aba para pegar as ligas do usuário
        const leagues = await fetchPlayerStatus();
        for (const leagueId in leagues) {
            const league = leagues[leagueId];
            const option = new Option(league.name, leagueId);
            leagueSelect.add(option);
        }
    } catch (error) {
        console.error("Erro ao carregar ligas para o contexto:", error);
    }
}

async function handleDepthChartSelection() {
    const teamSelect = document.getElementById('select-nfl-team').value;
    const leagueSelect = document.getElementById('select-league-context').value;
    const container = document.getElementById('depth-chart-container');
    const loading = document.getElementById('depth-chart-loading');

    if (!teamSelect) {
        container.classList.add('hidden');
        return;
    }
    
    loading.classList.remove('hidden');
    container.classList.add('hidden');

    try {
        const data = await fetchDepthChart(teamSelect, leagueSelect);
        renderDepthChart(data.chart, data.current_user_id, teamSelect);
        container.classList.remove('hidden');
    } catch (error) {
        console.error(error);
        container.innerHTML = `<div class="error"><p>${error.message}</p></div>`;
        container.classList.remove('hidden');
    } finally {
        loading.classList.add('hidden');
    }
}

function renderDepthChart(chartData, currentUserId, teamName) {
    const header = document.getElementById('depth-chart-header');
    const tableContainer = document.getElementById('depth-chart-table-container');
    
    header.textContent = `Depth Chart - ${teamName}`;
    
    const posicoesOrdenadas = Object.keys(chartData).sort((a, b) => (POSICAO_ORDEM[a] || 99) - (POSICAO_ORDEM[b] || 99));

    let tableHtml = `
        <table class="min-w-full bg-white divide-y divide-gray-200">
            <thead class="bg-gray-800">
                <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium text-white uppercase tracking-wider">Posição</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-white uppercase tracking-wider">Jogador 1</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-white uppercase tracking-wider">Jogador 2</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-white uppercase tracking-wider">Jogador 3</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-white uppercase tracking-wider">Jogador 4</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
    `;

    posicoesOrdenadas.forEach(pos => {
        const players = chartData[pos];
        tableHtml += `<tr><td class="px-6 py-4 font-bold bg-gray-100">${pos}</td>`;
        for (let i = 0; i < 4; i++) {
            if (players[i]) {
                const player = players[i];
                let statusClass = 'text-gray-500'; // Free Agent
                if (player.owner_id) {
                    statusClass = player.owner_id === currentUserId ? 'text-green-600 font-semibold' : 'text-yellow-600';
                }
                const injuryStatus = player.injury ? `<span class="text-red-500 text-xs ml-1">(${player.injury})</span>` : '';
                tableHtml += `<td class="px-6 py-4 whitespace-nowrap"><span class="${statusClass}">${player.name}</span>${injuryStatus}</td>`;
            } else {
                tableHtml += `<td class="px-6 py-4">-</td>`;
            }
        }
        tableHtml += `</tr>`;
    });

    tableHtml += `</tbody></table>`;
    tableContainer.innerHTML = tableHtml;
}