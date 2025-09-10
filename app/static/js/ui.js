import { createPlayerCardComponent, createLeagueElement } from './components.js';
import { fetchPlayerStatus, fetchTopPlayers, fetchPlayerDetails, searchPlayers, fetchNflTeams, fetchDepthChart, fetchAllLeagues } from './api.js';

// Estado da UI
const appState = { expandedState: {} };
const POSITIONS = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF', 'DL', 'LB', 'DB'];
const STATUS_ORDER = { 'PUP': 0, 'IR': 1, 'Suspended': 2, 'OUT': 3, 'Doubtful': 4, 'Questionable': 5, 'Probable': 6 };

// --- Aba "Status Player" ---
export async function loadPlayerStatus(forceRefresh = false, showBestBall = false) {
    const container = document.getElementById('leagues-container');
    const noIssues = document.getElementById('no-issues-message');
    const reloadBtn = document.getElementById('reload-btn');
    
    // --- INÍCIO DA NOVA LÓGICA ---
    // Seleciona os botões das outras abas
    const findForPlayerTab = document.querySelector('.tab-btn[data-tab="find-player"]');
    const depthChartTab = document.querySelector('.tab-btn[data-tab="depth-chart"]');

    // Desabilita o botão de reload e as outras abas
    reloadBtn.disabled = true;
    if (findForPlayerTab) findForPlayerTab.disabled = true;
    if (depthChartTab) depthChartTab.disabled = true;
    // --- FIM DA NOVA LÓGICA ---
    
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
        // --- INÍCIO DA LÓGICA MODIFICADA ---
        // Reabilita o botão de reload e as outras abas
        reloadBtn.disabled = false;
        if (findForPlayerTab) findForPlayerTab.disabled = false;
        if (depthChartTab) depthChartTab.disabled = false;
        // --- FIM DA LÓGICA MODIFICADA ---
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
            // A API agora retorna uma lista de objetos: [{abbr: 'PIT', name: 'Pittsburgh Steelers'}, ...]
            const teams = await fetchNflTeams(); 
            
            // Loop modificado para usar a nova estrutura de dados
            teams.forEach(team => {
                // O valor da opção é a abreviação (ex: 'PIT')
                // O texto exibido é o nome completo (ex: 'Pittsburgh Steelers')
                const option = new Option(team.name, team.abbr);
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
        // ANTES: usava fetchPlayerStatus() que retorna dados filtrados
        // AGORA: usa a nova função fetchAllLeagues() para buscar TODAS as ligas
        const leagues = await fetchAllLeagues();
        
        // A nova API retorna um array simples de ligas, então o loop é mais direto
        leagues.forEach(league => {
            const option = new Option(league.name, league.league_id);
            leagueSelect.add(option);
        });

    } catch (error) {
        console.error("Erro ao carregar todas as ligas para o contexto:", error);
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

    // A estrutura da tabela agora usa classes CSS personalizadas
    let tableHtml = `
        <table class="depth-chart-table">
            <thead>
                <tr>
                    <th>Posição</th>
                    <th>Jogador 1</th>
                    <th>Jogador 2</th>
                    <th>Jogador 3</th>
                    <th>Jogador 4</th>
                </tr>
            </thead>
            <tbody>
    `;

    posicoesOrdenadas.forEach(pos => {
        const players = chartData[pos];
        tableHtml += `<tr><td class="position-cell">${pos}</td>`;
        for (let i = 0; i < 4; i++) {
            if (players[i]) {
                const player = players[i];
                // A lógica para as classes de status foi simplificada
                let statusClass = 'status-free-agent'; // Classe padrão para Free Agent
                if (player.owner_id) {
                    statusClass = player.owner_id === currentUserId ? 'status-owned-by-user' : 'status-owned-by-other';
                }
                const injuryStatus = player.injury ? `<span class="injury-status">(${player.injury})</span>` : '';
                tableHtml += `<td><span class="${statusClass}">${player.name}</span>${injuryStatus}</td>`;
            } else {
                tableHtml += `<td>-</td>`;
            }
        }
        tableHtml += `</tr>`;
    });

    tableHtml += `</tbody></table>`;
    tableContainer.innerHTML = tableHtml;
}