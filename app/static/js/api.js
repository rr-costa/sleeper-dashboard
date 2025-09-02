export async function fetchPlayerStatus(forceRefresh = false) {
    const endpoint = forceRefresh ? '/api/refresh-league-status' : '/api/player-status';
    const response = await fetch(endpoint);
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
    if (!response.ok) throw new Error(`Error: ${response.status}`);
    return await response.json();
}