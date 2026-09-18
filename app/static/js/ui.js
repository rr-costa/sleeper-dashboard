import { createPlayerCardComponent, createLeagueElement } from './components.js';
import { fetchPlayerStatus, fetchTopPlayers, fetchPlayerDetails, searchPlayers, fetchNflTeams, fetchDepthChart, fetchAllLeagues } from './api.js';

// Estado da UI
const appState = { expandedState: {} };
const POSITIONS = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF', 'DL', 'LB', 'DB'];
const STATUS_ORDER = { 'PUP': 0, 'IR': 1, 'Bye': 2, 'Suspended': 3, 'OUT': 4, 'Doubtful': 5, 'Questionable': 6, 'Probable': 7 };

// --- Aba "Status Player" ---
export async function loadPlayerStatus(forceRefresh = false, showBestBall = false) {
    const container = document.getElementById('leagues-container');
    const noIssues = document.getElementById('no-issues-message');
    const reloadBtn = document.getElementById('reload-btn');
    const findForPlayerTab = document.querySelector('.tab-btn[data-tab="find-player"]');
    const depthChartTab = document.querySelector('.tab-btn[data-tab="depth-chart"]');

    reloadBtn.disabled = true;
    if (findForPlayerTab) findForPlayerTab.disabled = true;
    if (depthChartTab) depthChartTab.disabled = true;

    reloadBtn.textContent = 'Loading...';
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
        if (findForPlayerTab) findForPlayerTab.disabled = false;
        if (depthChartTab) depthChartTab.disabled = false;
        reloadBtn.textContent = '↻ Reload';
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
                playerName: player.name,
                leagues: player.leagues,
                position: player.position,
                injuryStatus: player.injury_status,
                byeWeek: player.bye_week
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

        if (!data || data.error) {
            resultsContainer.innerHTML = `<div class="no-results">${player.name} not found or error: ${data?.error || 'Unknown error'}</div>`;
            return;
        }

        const cardData = {
            playerName: player.name,
            leagues: data.leagues,
            position: data.position || '?',
            injuryStatus: data.injury_status || 'Active',
            otherLeagues: data.other_leagues || [],
            byeWeek: data.bye_week || null
        };

        const card = createPlayerCardComponent(cardData);
        resultsContainer.innerHTML = '';
        resultsContainer.appendChild(card);
    } catch (error) {
        resultsContainer.innerHTML = `<div class="error"><p>Error: ${error.message}</p></div>`;
    }
}

function debounce(func, wait) {
    let timeout;
    return function (...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

// --- Aba "Depth Chart" ---
const POSICAO_ORDEM = {
    'QB': 1, 'RB': 2, 'WR': 3, 'TE': 4, 'K': 5, 'DEF': 6,
    'DL': 7, 'DE': 8, 'DT': 9, 'NT': 10,
    'LB': 11, 'ILB': 12,
    'DB': 13, 'CB': 14, 'S': 15, 'SS': 16, 'FS': 17
};

export async function initDepthChartTab() {
    const teamSelect = document.getElementById('select-nfl-team');

    if (teamSelect.options.length <= 1) {
        try {
            const teams = await fetchNflTeams();
            teams.forEach(team => {
                const option = new Option(team.name, team.abbr);
                teamSelect.add(option);
            });
        } catch (error) {
            console.error(error);
        }
    }

    const leagueSelect = document.getElementById('select-league-context');
    populateLeagueContextSelect();
    teamSelect.addEventListener('change', handleDepthChartSelection);
    leagueSelect.addEventListener('change', handleDepthChartSelection);
}

async function populateLeagueContextSelect() {
    const leagueSelect = document.getElementById('select-league-context');
    if (leagueSelect.options.length > 1) return;

    try {
        const leagues = await fetchAllLeagues();
        leagues.forEach(league => {
            const option = new Option(league.name, league.league_id);
            leagueSelect.add(option);
        });
    } catch (error) {
        console.error('Erro ao carregar todas as ligas para o contexto:', error);
    }
}

async function handleDepthChartSelection() {
    const teamSelect = document.getElementById('select-nfl-team');
    const leagueSelect = document.getElementById('select-league-context').value;
    const container = document.getElementById('depth-chart-container');
    const loading = document.getElementById('depth-chart-loading');

    const teamAbbr = teamSelect.value;
    const teamFullName = teamSelect.options[teamSelect.selectedIndex].text;

    if (!teamAbbr) {
        container.classList.add('hidden');
        return;
    }

    loading.classList.remove('hidden');
    container.classList.add('hidden');

    try {
        const data = await fetchDepthChart(teamAbbr, leagueSelect);
        renderDepthChart(data.chart, data.current_user_id, teamFullName);
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

    header.textContent = `Depth Chart - ${teamName} (by Sleeper.app)`;

    const legendHtml = `
        <div class="depth-chart-legend" style="margin: 10px 0; padding: 8px; background: #f8f9fa; border-radius: 4px; font-size: 14px;">
            <span style="margin-right: 15px;">
                <span class="status-owned-by-user" style="padding: 2px 6px; border-radius: 3px; margin-right: 5px;">Your Roster</span>
                <span class="status-owned-by-other" style="padding: 2px 6px; border-radius: 3px; margin-right: 5px;">Other Rosters</span>
                <span class="status-free-agent" style="padding: 2px 6px; border-radius: 3px; margin-right: 5px;">Free Agent</span>
            </span>
        </div>
    `;

    const allPlayers = [];
    Object.entries(chartData).forEach(([depthChartPosition, players]) => {
        players.forEach(player => {
            allPlayers.push({
                ...player,
                depth_chart_position: depthChartPosition,
                position: player.position || 'UNK'
            });
        });
    });

    const { jogadoresAgrupados, posicoesOrdenadas } = agruparEOrdenarJogadores(allPlayers);

    let tableHtml = `
        <table class="depth-chart-table">
            <thead>
                <tr>
                    <th>Posição</th>
                    <th>Jogador 1</th>
                    <th>Jogador 2</th>
                    <th>Jogador 3</th>
                    <th>Jogador 4</th>
                    <th>Jogador 5</th>
                </tr>
            </thead>
            <tbody>
    `;

    posicoesOrdenadas.forEach(posicao => {
        const jogadoresPosicao = jogadoresAgrupados[posicao] || [];

        tableHtml += '<tr class="fade-in">';
        tableHtml += `<td class="position-cell">${posicao}</td>`;

        for (let i = 0; i < 5; i++) {
            const jogador = jogadoresPosicao[i];
            if (jogador) {
                let statusClass = 'status-free-agent';
                if (jogador.owner_id) {
                    statusClass = jogador.owner_id === currentUserId ? 'status-owned-by-user' : 'status-owned-by-other';
                }

                const injuryStatus = jogador.injury ? `<span class="injury-status">(${jogador.injury})</span>` : '';
                tableHtml += `<td><span class="${statusClass}">${jogador.name}</span>${injuryStatus}</td>`;
            } else {
                tableHtml += '<td>-</td>';
            }
        }

        tableHtml += '</tr>';
    });

    tableHtml += '</tbody></table>';
    tableContainer.innerHTML = legendHtml + tableHtml;
}

function agruparEOrdenarJogadores(jogadores) {
    const jogadoresAgrupados = {};

    if (!jogadores || !Array.isArray(jogadores)) {
        return { jogadoresAgrupados: {}, posicoesOrdenadas: [] };
    }

    jogadores.forEach(jogador => {
        if (!jogador) return;
        const pos = jogador.depth_chart_position || jogador.position || 'UNK';
        if (!jogadoresAgrupados[pos]) {
            jogadoresAgrupados[pos] = [];
        }
        jogadoresAgrupados[pos].push(jogador);
    });

    const posicoesOrdenadas = Object.keys(jogadoresAgrupados).sort((a, b) => {
        const getMainPosition = (depthPos) => {
            if (depthPos.includes('QB')) return 'QB';
            if (depthPos.includes('RB')) return 'RB';
            if (depthPos.includes('WR')) return 'WR';
            if (depthPos.includes('TE')) return 'TE';
            if (depthPos.includes('K')) return 'K';
            if (depthPos.includes('DEF')) return 'DEF';
            if (depthPos.includes('DL')) return 'DL';
            if (depthPos.includes('DE')) return 'DE';
            if (depthPos.includes('DT')) return 'DT';
            if (depthPos.includes('LB')) return 'LB';
            if (depthPos.includes('DB')) return 'DB';
            if (depthPos.includes('CB')) return 'CB';
            if (depthPos.includes('S')) return 'S';
            return depthPos;
        };

        const mainPosA = getMainPosition(a);
        const mainPosB = getMainPosition(b);

        const ordemA = POSICAO_ORDEM[mainPosA] || 99;
        const ordemB = POSICAO_ORDEM[mainPosB] || 99;

        if (ordemA !== ordemB) {
            return ordemA - ordemB;
        }

        return a.localeCompare(b);
    });

    posicoesOrdenadas.forEach(pos => {
        if (jogadoresAgrupados[pos]) {
            jogadoresAgrupados[pos].sort((a, b) => {
                const orderA = a.order || a.depth_chart_order || Infinity;
                const orderB = b.order || b.depth_chart_order || Infinity;
                return orderA - orderB;
            });
        }
    });

    return { jogadoresAgrupados, posicoesOrdenadas };
}
