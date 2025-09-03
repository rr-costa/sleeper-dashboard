export async function fetchPlayerStatus(forceRefresh = false, showBestBall = false) {
    const endpoint = forceRefresh ? '/api/refresh-league-status' : '/api/player-status';
    const url = `${endpoint}?showBestBall=${showBestBall}`;
    const response = await fetch(url);
    if (!response.ok) throw new Error(`Server error: ${response.status}`);
    return await response.json();
}

export async function fetchTopPlayers() {
    const response = await fetch('/api/top-players');
    if (!response.ok) throw new Error('Failed to load top players');
    return await response.json();
}

export async function searchPlayers(query, positions) {
    const params = new URLSearchParams({ query });
    positions.forEach(pos => params.append('positions', pos));
    const response = await fetch(`/api/search-players?${params}`);
    if (!response.ok) throw new Error('Search failed');
    return await response.json();
}

export async function fetchPlayerDetails(playerName) {
    const params = new URLSearchParams({ name: playerName });
    const response = await fetch(`/api/player-details?${params}`);
    if (!response.ok) {
        throw new Error(`Error: ${response.status}`);
    }
    const data = await response.json();
    
    // Garantir que temos um nome válido no retorno
    if (data && !data.player_name && data.name) {
        data.player_name = data.name;
    }
    
    return data;
}