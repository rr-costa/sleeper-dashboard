const STATUS_CLASSES = {
    'Active': 'active', 'Probable': 'probable', 'Questionable': 'questionable',
    'Doubtful': 'doubtful', 'OUT': 'out', 'IR': 'ir',
    'Suspended': 'suspended', 'PUP': 'pup'
};
export function createPlayerCardComponent(playerData) {
    const { playerName, leagues, position, injuryStatus, otherLeagues } = playerData;
    const statusText = injuryStatus || 'Active';
    const statusClass = STATUS_CLASSES[statusText] || '';

    const card = document.createElement('div');
    card.className = 'top-player-card';

    const cardHTML = `
        <div class="player-header">
            <h4>${playerName}</h4>
            <span class="badge">${leagues.length} leagues</span>
        </div>
        <div class="player-status">
            <span class="player-position">${position || '?'}</span>
            <span class="status-tag ${statusClass}">${statusText}</span>
        </div>
        
        <div class="player-leagues">
            ${leagues.slice(0, 3).map(league => `
                <div class="league-item">
                    <span>${league.league_name}</span>
                    <span>${league.roster_position || 'BN'}</span>
                </div>
            `).join('')}
        </div>
        
        ${otherLeagues && otherLeagues.length > 0 ? `
            <hr class="separator">
            <a href="#" class="other-leagues-toggle-link">show other leagues situation</a>
            <div class="other-leagues-section hidden">
                <div class="other-leagues-list"></div>
                <div class="pagination-controls"></div>
            </div>
        ` : ''}
    `;

    card.innerHTML = cardHTML;

    // Lógica para o botão 'more' da seção original
    if (leagues.length > 3) {
        const extraLeagues = document.createElement('div');
        extraLeagues.className = 'extra-leagues hidden';
        extraLeagues.innerHTML = leagues.slice(3).map(league => `
            <div class="league-item">
                <span>${league.league_name}</span>
                <span>${league.roster_position || 'BN'}</span>
            </div>
        `).join('');
        card.querySelector('.player-leagues').appendChild(extraLeagues);

        const moreButton = document.createElement('div');
        moreButton.className = 'more-leagues';
        moreButton.textContent = `+${leagues.length - 3} more`;
        moreButton.onclick = () => {
            const isHidden = extraLeagues.classList.contains('hidden');
            extraLeagues.classList.toggle('hidden', !isHidden);
            moreButton.textContent = isHidden ? '- show less' : `+${leagues.length - 3} more`;
        };
        card.querySelector('.player-leagues').appendChild(moreButton);
    }
    
    // Lógica para a nova seção de "outras ligas"
    if (otherLeagues && otherLeagues.length > 0) {
        const toggleLink = card.querySelector('.other-leagues-toggle-link');
        const otherLeaguesSection = card.querySelector('.other-leagues-section');
        const otherLeaguesList = card.querySelector('.other-leagues-list');
        const paginationControls = card.querySelector('.pagination-controls');
        
        let currentPage = 0;
        const itemsPerPage = 5;

        const renderLeagues = () => {
            const start = currentPage * itemsPerPage;
            const end = start + itemsPerPage;
            const visibleItems = otherLeagues.slice(0, end);
            
            otherLeaguesList.innerHTML = visibleItems.map(league => `
                <div class="league-item">
                    <span>${league.league_name}</span>
                    <span>${league.status}</span>
                </div>
            `).join('');

            // Lógica para os botões de paginação
            paginationControls.innerHTML = '';
            const totalRemaining = otherLeagues.length - visibleItems.length;

            if (totalRemaining > 0) {
                const moreBtn = document.createElement('div');
                moreBtn.className = 'more-leagues';
                moreBtn.textContent = `+${totalRemaining} more`;
                moreBtn.onclick = () => {
                    currentPage++;
                    renderLeagues();
                };
                paginationControls.appendChild(moreBtn);
            } else if (otherLeagues.length > itemsPerPage) {
                const lessBtn = document.createElement('div');
                lessBtn.className = 'more-leagues';
                lessBtn.textContent = '- show less';
                lessBtn.onclick = () => {
                    currentPage = 0;
                    renderLeagues();
                };
                paginationControls.appendChild(lessBtn);
            }
        };

        toggleLink.onclick = (e) => {
            e.preventDefault();
            const isHidden = otherLeaguesSection.classList.contains('hidden');
            otherLeaguesSection.classList.toggle('hidden', !isHidden);
            toggleLink.textContent = isHidden ? 'hide other leagues situation' : 'show other leagues situation';
            
            if (isHidden) {
                currentPage = 0;
                renderLeagues();
            }
        };
    }
   
    return card;
}
/*
export function createPlayerCardComponent(playerData) {
    const { playerName, leagues, position, injuryStatus } = playerData;
    const statusText = injuryStatus || 'Active';
    const statusClass = STATUS_CLASSES[statusText] || '';

    const card = document.createElement('div');
    card.className = 'top-player-card';
    card.innerHTML = `
        <div class="player-header">
            <h4>${playerName}</h4>
            <span class="badge">${leagues.length} leagues</span>
        </div>
        <div class="player-status">
            <span class="player-position">${position || '?'}</span>
            <span class="status-tag ${statusClass}">${statusText}</span>
        </div>
        <div class="player-leagues">
            ${leagues.slice(0, 3).map(league => `
                <div class="league-item">
                    <span>${league.league_name}</span>
                    <span>${league.roster_position || 'BN'}</span>
                </div>
            `).join('')}
        </div>
    `;

    if (leagues.length > 3) {
        const extraLeagues = document.createElement('div');
        extraLeagues.className = 'extra-leagues';
        extraLeagues.style.display = 'none';
        extraLeagues.innerHTML = leagues.slice(3).map(league => `
            <div class="league-item">
                <span>${league.league_name}</span>
                <span>${league.roster_position || 'BN'}</span>
            </div>
        `).join('');
        card.querySelector('.player-leagues').appendChild(extraLeagues);

        const moreButton = document.createElement('div');
        moreButton.className = 'more-leagues';
        moreButton.textContent = `+${leagues.length - 3} more`;
        moreButton.onclick = () => {
            const isHidden = extraLeagues.style.display === 'none';
            extraLeagues.style.display = isHidden ? 'block' : 'none';
            moreButton.textContent = isHidden ? '- show less' : `+${leagues.length - 3} more`;
        };
        card.querySelector('.player-leagues').appendChild(moreButton);
    }
    return card;
}
*/

export function createLeagueElement(leagueId, league, expandedState) {
    const isExpanded = expandedState[leagueId]?.expanded || false;
    const leagueEl = document.createElement('div');
    leagueEl.className = 'league-card';
    leagueEl.dataset.leagueId = leagueId;
    leagueEl.innerHTML = `
        <div class="league-header" data-expanded="${isExpanded}">
            <div class="league-info">
                <h3>${league.name}</h3>
                <span class="badge">${league.total_issues} issues</span>
            </div>
            <span class="toggle-icon">${isExpanded ? '▲' : '▼'}</span>
        </div>
        <div class="league-content" style="display: ${isExpanded ? 'block' : 'none'}">
            ${renderStatusGroups(leagueId, league.issues, expandedState)}
        </div>
    `;
    return leagueEl;
}

function renderStatusGroups(leagueId, issues, expandedState) {
    return issues.map(issue => {
        const isExpanded = expandedState[leagueId]?.statuses?.[issue.status] || false;
        return `
            <div class="status-group">
                <div class="group-header" data-status="${issue.status}" data-expanded="${isExpanded}">
                    <div class="group-info">
                        <h4>${issue.status}</h4>
                        <span class="badge">${issue.count}</span>
                    </div>
                    <span class="toggle-icon">${isExpanded ? '▲' : '▼'}</span>
                </div>
                <div class="group-content" style="display: ${isExpanded ? 'block' : 'none'}">
                    ${renderGroupContent(issue)}
                </div>
            </div>
        `;
    }).join('');
}

function renderGroupContent(issue) {
    if (issue.is_empty) {
        return `<div class="empty-positions">${issue.positions.map(pos => `<div class="position-tag">${pos}</div>`).join('')}</div>`;
    }
    return `<div class="player-list">
        ${issue.players.map(player => `
            <div class="player-card">
                <div class="player-info">
                    <strong>${player.name}</strong>
                    <span>${player.position} - ${player.team}</span>
                </div>
                <span class="status-tag ${STATUS_CLASSES[player.status] || ''}">${player.status}</span>
            </div>
        `).join('')}
    </div>`;
}