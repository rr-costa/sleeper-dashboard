import requests
from flask import current_app
from concurrent.futures import ThreadPoolExecutor
from . import utils
import time
import logging
from collections import defaultdict

# --- FUNÇÕES DE REQUEST À API SLEEPER ---
def sleeper_request(url, timeout=10):
    """
    Faz um pedido à API do Sleeper com lógica de retry.
    Tenta até 3 vezes com um segundo de espera entre as falhas.
    """
    for attempt in range(3):
        try:
            response = requests.get(url, timeout=timeout)
            if response.status_code == 200:
                return response.json()
            
            # Se o status não for 200, regista o aviso e tenta novamente
            logging.warning(f"Request failed on attempt {attempt + 1}/3: {url} - Status {response.status_code}")

        except requests.exceptions.RequestException as e:
            # Se for um erro de rede/timeout, regista o erro e tenta novamente
            logging.error(f"Request error on attempt {attempt + 1}/3: {url} - {str(e)}")
        
        # Espera 1 segundo antes da próxima tentativa
        time.sleep(1)
        
    # Se todas as 3 tentativas falharem, retorna None
    logging.error(f"All 3 attempts failed for URL: {url}")
    return None

def get_user_id(username):
    user_data = sleeper_request(f'https://api.sleeper.app/v1/user/{username}', timeout=5)
    return user_data.get('user_id') if user_data else None

# --- FUNÇÕES DE DADOS COM CACHE ---
def get_all_players():
    try:
        cached_data, _ = utils.load_players_from_disk()
        if cached_data:
            return cached_data
            
        players = sleeper_request(f"https://api.sleeper.app/v1/players/{current_app.config['SPORT']}", timeout=15)
        if not players:
            logging.warning("Resposta vazia da API de jogadores")
            return {}
            
        active_players = {
            pid: pdata for pid, pdata in players.items() if pdata.get('active') is True
        }
        
        utils.save_players_to_disk(active_players)
        return active_players
    except Exception as e:
        logging.error(f"Erro ao buscar jogadores: {str(e)}", exc_info=True)
        return {}

def get_cached_leagues(user_id):
    cache_key = (user_id, current_app.config['CURRENT_SEASON'])
    if cache_key in utils.LEAGUE_CACHE:
        return utils.LEAGUE_CACHE[cache_key]
    
    leagues = sleeper_request(f"https://api.sleeper.app/v1/user/{user_id}/leagues/nfl/{current_app.config['CURRENT_SEASON']}") or []
    utils.LEAGUE_CACHE[cache_key] = leagues
    return leagues

def get_cached_rosters(league_id):
    if league_id in utils.LEAGUE_CACHE:
        return utils.LEAGUE_CACHE[league_id]
    
    rosters = sleeper_request(f'https://api.sleeper.app/v1/league/{league_id}/rosters') or []
    utils.LEAGUE_CACHE[league_id] = rosters
    return rosters

def get_league_settings(league_id):
    cache_key = f"settings_{league_id}"
    if cache_key in utils.LEAGUE_CACHE:
        return utils.LEAGUE_CACHE[cache_key]
    
    settings = sleeper_request(f'https://api.sleeper.app/v1/league/{league_id}')
    if settings:
        utils.LEAGUE_CACHE[cache_key] = settings
    return settings

# --- PROCESSAMENTO DE DADOS ---
def _process_empty_positions(starters, roster_positions):
    return [
        roster_positions[i] if i < len(roster_positions) else f"Position {i+1}"
        for i, player_id in enumerate(starters)
        if not player_id or player_id in ['None', '0']
    ]

def _process_player_status(player_id, all_players):
    if not player_id or player_id in ['None', '0', '']:
        return None, None
    
    player = all_players.get(player_id)
    if player is None:
        return {'full_name': f'Unknown Player ({player_id})', 'position': '?', 'team': '?', 'injury_status': 'Unknown'}, 'Unknown'

    try:
        full_name = player.get('full_name')
        if not full_name:
            # Construir nome se full_name não estiver disponível
            first_name = player.get('first_name', '')
            last_name = player.get('last_name', '')
            full_name = f"{first_name} {last_name}".strip() or f"Player_{player_id[:6]}"
        
        position = player.get('position') or '?'
        team = player.get('team') or '?'
        injury_status = player.get('injury_status') or player.get('status') or 'Active'
        
        safe_player = {'full_name': full_name, 'position': position, 'team': team, 'injury_status': injury_status}
        status = injury_status if injury_status != 'Active' else None
        return safe_player, status
    except Exception as e:
        logging.warning(f"Error processing player {player_id}: {str(e)}")
        return {'full_name': f'Player_{player_id[:6]}', 'position': '?', 'team': '?', 'injury_status': 'Unknown'}, 'Unknown'

def get_starters_with_status(user_id, force_refresh=False, show_best_ball=False):
    if force_refresh:
        utils.LEAGUE_CACHE.clear()
        
    leagues = get_cached_leagues(user_id)
    all_players = get_all_players()
    leagues_data = {}
    
    for league in leagues:
        league_id = league['league_id']
        with ThreadPoolExecutor() as executor:
            settings_future = executor.submit(get_league_settings, league_id)
            rosters_future = executor.submit(get_cached_rosters, league_id)
            league_settings, rosters = settings_future.result(), rosters_future.result()
        
        if not league_settings or not rosters: continue
        if not league.get('status') == 'in_season': continue  # Apenas ligas na temporada   
        if not show_best_ball and  not league.get('settings', {}).get('best_ball') == 0: continue #remove ligas best ball
        

        roster_positions = league_settings.get('roster_positions', [])
        league_issues, total_issues = [], 0
        user_rosters = [r for r in rosters if r.get('owner_id') == user_id]
        
        for roster in user_rosters:
            starters = roster.get('starters', []) or []
            empty_positions = _process_empty_positions(starters, roster_positions)
            if empty_positions:
                league_issues.append({'status': 'Empty Position', 'positions': empty_positions, 'count': len(empty_positions), 'is_empty': True})
                total_issues += len(empty_positions)
            
            status_groups = {}
            for player_id in starters:
                player, status = _process_player_status(player_id, all_players)
                if status:
                    status_groups.setdefault(status, []).append({
                        'id': player_id, 'name': player.get('full_name'), 'position': player.get('position'),
                        'team': player.get('team'), 'status': status
                    })
            
            for status in current_app.config['STATUS_CONFIG']:
                if status in status_groups:
                    league_issues.append({'status': status, 'players': status_groups[status], 'count': len(status_groups[status])})
                    total_issues += len(status_groups[status])
        
        if league_issues:
            leagues_data[league_id] = {'name': league['name'], 'issues': league_issues, 'total_issues': total_issues}
    
    return leagues_data

def get_roster_position(player_id, roster, league_id):
    reserve, starters, taxi = roster.get('reserve') or [], roster.get('starters') or [], roster.get('taxi') or []
    if player_id in reserve: return "IR"
    if player_id in taxi: return "TS"
    if player_id in starters:
        try:
            idx = starters.index(player_id)
            # Adicionada verificação para o caso de settings ser None
            settings = get_league_settings(league_id)
            if settings:
                roster_positions = settings.get('roster_positions', [])
                return roster_positions[idx] if idx < len(roster_positions) else "ST"
            return "ST"  # Retorna "ST" como fallback se as settings falharem
        except (ValueError, IndexError): return "ST"
    return "BN"

def get_nfl_teams():
    """Busca e retorna uma lista de todos os times da NFL a partir do cache de jogadores."""
    all_players = get_all_players()
    if not all_players:
        return []
    
    teams = set()
    for player in all_players.values():
        if player.get('team'):
            teams.add(player['team'])
            
    return sorted(list(teams))

def get_nfl_depth_chart(team_abbr, league_id=None):
    """
    Monta o depth chart para um time da NFL e enriquece com dados de uma liga específica.
    """
    all_players = get_all_players()
    if not all_players:
        return {}

    # 1. Filtra jogadores do time selecionado
    team_players = [p for p in all_players.values() if p.get('team') == team_abbr and p.get('active')]

    # 2. Obtém dados da liga, se um league_id for fornecido
    league_players = {}
    if league_id:
        rosters = get_cached_rosters(league_id)
        if rosters:
            for roster in rosters:
                owner_id = roster.get('owner_id')
                for player_id in roster.get('players', []):
                    league_players[player_id] = owner_id

    # 3. Agrupa jogadores por posição e enriquece com dados da liga
    depth_chart = defaultdict(list)
    for player in team_players:
        pos = player.get('depth_chart_position') or player.get('position')
        if not pos:
            continue

        player_id = player.get('player_id')
        owner_id = league_players.get(player_id) if league_id else None

        depth_chart[pos].append({
            'name': player.get('full_name', f"{player.get('first_name', '')} {player.get('last_name', '')}".strip()),
            'order': player.get('depth_chart_order'),
            'injury': player.get('injury_status'),
            'owner_id': owner_id
        })
    
    # 4. Ordena os jogadores dentro de cada posição
    for pos in depth_chart:
        depth_chart[pos].sort(key=lambda x: (x['order'] if x['order'] is not None else float('inf')))
        
    return depth_chart