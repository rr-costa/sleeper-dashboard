from flask import Flask, render_template, request, session, redirect, url_for, jsonify
import requests
import os
import logging
import json
import time as time_module
from datetime import datetime, timedelta, time
from functools import wraps
from dotenv import load_dotenv
from cachetools import TTLCache
from concurrent.futures import ThreadPoolExecutor, as_completed


load_dotenv()

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'secret_key_default')
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=True,
    PERMANENT_SESSION_LIFETIME=timedelta(hours=1),
    SESSION_REFRESH_EACH_REQUEST=True
)

# Configurações
SPORT = 'nfl'
CURRENT_SEASON = "2025"
TOPN = 6
CACHE_DIR = 'cache'
PLAYERS_CACHE_FILE = os.path.join(CACHE_DIR, 'players_cache.json')

# Certifique-se de que o diretório de cache existe
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

# Configuração unificada de status
STATUS_CONFIG = {
    'PUP': {'order': 0, 'abbr': 'PUP'},
    'IR': {'order': 1, 'abbr': 'IR'},
    'Suspended': {'order': 2, 'abbr': 'S'},
    'OUT': {'order': 3, 'abbr': 'O'},
    'Doubtful': {'order': 4, 'abbr': 'D'},
    'Questionable': {'order': 5, 'abbr': 'Q'},
    'Probable': {'order': 6, 'abbr': 'P'}
}

# Ordem das posições para exibição
POSITION_ORDER = ['QB', 'RB', 'WR', 'TE', 'K', 'DST', 'DL', 'LB', 'DB']

# Caches com TTLCache
PLAYERS_CACHE = TTLCache(maxsize=1, ttl=600)  # 10 minutos
LEAGUE_CACHE = TTLCache(maxsize=100, ttl=300)  # 5 minutos

def is_night_time():
    """Verifica se está no período noturno (23h às 6h)"""
    now = datetime.now().time()
    return now >= time(23, 0) or now < time(6, 0)

def is_morning_time():
    """Verifica se está no período da manhã (6h às 10h)"""
    now = datetime.now().time()
    return time(6, 0) <= now < time(10, 0)

def get_cache_ttl():
    """Calcula o TTL apropriado baseado no horário atual"""
    if is_night_time():
        # Calcula quanto tempo falta até as 6h
        now = datetime.now()
        next_6am = (now + timedelta(days=1)).replace(hour=6, minute=0, second=0, microsecond=0)
        if now.hour >= 23:
            next_6am = now.replace(hour=6, minute=0, second=0, microsecond=0) + timedelta(days=1)
        return (next_6am - now).total_seconds()
    elif is_morning_time():
        return 3600  # 1 hora
    else:
        return 600   # 10 minutos

def load_players_from_disk():
    """Carrega jogadores do cache em disco se estiver válido"""
    try:
        if not os.path.exists(PLAYERS_CACHE_FILE):
            return None, 0
            
        mod_time = os.path.getmtime(PLAYERS_CACHE_FILE)
        current_time = time_module.time()
        
        # Verifica se o cache foi criado durante a noite
        mod_datetime = datetime.fromtimestamp(mod_time)
        mod_was_night = mod_datetime.hour >= 23 or mod_datetime.hour < 6
        
        if mod_was_night and is_night_time():
            # Cache noturno é sempre válido durante a noite
            with open(PLAYERS_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f), mod_time
                
        # Para outros casos, usa TTL padrão baseado no horário atual
        ttl = get_cache_ttl()
        if current_time - mod_time < ttl:
            with open(PLAYERS_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f), mod_time
                
        return None, mod_time
        
    except Exception as e:
        app.logger.error(f"Erro ao ler cache de jogadores: {str(e)}")
        return None, 0

def save_players_to_disk(players_data):
    """Salva jogadores no cache em disco"""
    try:
        with open(PLAYERS_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(players_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        app.logger.error(f"Erro ao salvar cache de jogadores: {str(e)}")
        return False

# ==================== FUNÇÕES AUXILIARES ====================
def sleeper_request(url, timeout=10):
    """Wrapper para requests à API Sleeper com tratamento de erros"""
    try:
        response = requests.get(url, timeout=timeout)
        if response.status_code == 200:
            return response.json()
        app.logger.warning(f"Request failed: {url} - Status {response.status_code}")
        return None
    except Exception as e:
        app.logger.error(f"Request error: {url} - {str(e)}")
        return None

def get_all_players():
    """Obtém todos os jogadores ativos com cache baseado em horário"""
    try:
        # Tenta carregar do cache em disco
        cached_data, mod_time = load_players_from_disk()
        if cached_data:
            return cached_data
            
        # Busca da API se não tiver cache válido
        players = sleeper_request(f'https://api.sleeper.app/v1/players/{SPORT}', timeout=15)
        
        if not players:
            app.logger.warning("Resposta vazia da API de jogadores")
            return {}
            
        # Filtra apenas jogadores ativos
        active_players = {
            player_id: player_data
            for player_id, player_data in players.items()
            if player_data.get('active') is True
        }
        
        # Salva no disco
        save_players_to_disk(active_players)
        
        return active_players
        
    except Exception as e:
        app.logger.error(f"Erro ao buscar jogadores: {str(e)}", exc_info=True)
        return {}

def get_cached_leagues(user_id):
    """Obtém ligas com cache TTLCache"""
    cache_key = (user_id, CURRENT_SEASON)
    if cache_key in LEAGUE_CACHE:
        return LEAGUE_CACHE[cache_key]
    
    leagues = sleeper_request(f'https://api.sleeper.app/v1/user/{user_id}/leagues/nfl/{CURRENT_SEASON}', timeout=10) or []
    LEAGUE_CACHE[cache_key] = leagues
    return leagues

def get_cached_rosters(league_id):
    """Obtém rosters com cache TTLCache"""
    if league_id in LEAGUE_CACHE:
        return LEAGUE_CACHE[league_id]
    
    rosters = sleeper_request(f'https://api.sleeper.app/v1/league/{league_id}/rosters') or []
    LEAGUE_CACHE[league_id] = rosters
    return rosters

def get_league_settings(league_id):
    """Obtém as configurações da liga usando cache"""
    cache_key = f"settings_{league_id}"
    if cache_key in LEAGUE_CACHE:
        return LEAGUE_CACHE[cache_key]
    
    settings = sleeper_request(f'https://api.sleeper.app/v1/league/{league_id}')
    if settings:
        LEAGUE_CACHE[cache_key] = settings
    return settings

def get_user_id(username):
    """Obtém o ID do usuário pelo username do Sleeper"""
    user_data = sleeper_request(f'https://api.sleeper.app/v1/user/{username}', timeout=5)
    return user_data.get('user_id') if user_data else None

# ==================== PROCESSAMENTO DE STATUS ====================
def _process_empty_positions(starters, roster_positions):
    """Identifica posições vazias no lineup usando nomes reais"""
    empty = []
    for i, player_id in enumerate(starters):
        if not player_id or player_id in ['None', '0']:
            position_name = roster_positions[i] if i < len(roster_positions) else f"Position {i+1}"
            empty.append(position_name)
    return empty

def _process_player_status(player_id, all_players):
    """Processa status de um jogador individual com fallback robusto"""
    # Caso 1: player_id inválido
    if not player_id or player_id in ['None', '0', '']:
        return None, None
    
    # Caso 2: player não encontrado no dicionário
    player = all_players.get(player_id)
    if player is None:
        return {
            'full_name': f'Unknown Player ({player_id})',
            'position': '?',
            'team': '?',
            'injury_status': 'Unknown'
        }, 'Unknown'
    
    # Caso 3: player encontrado mas campos essenciais ausentes
    try:
        # Garante que temos valores padrão para todos os campos
        full_name = player.get('full_name') or f'Player_{player_id[:6]}'
        position = player.get('position') or '?'
        team = player.get('team') or '?'
        injury_status = player.get('injury_status') or player.get('status') or 'Active'
        
        # Prepara objeto player seguro
        safe_player = {
            'full_name': full_name,
            'position': position,
            'team': team,
            'injury_status': injury_status
        }
        
        # Determina status apenas se não for 'Active'
        status = injury_status if injury_status != 'Active' else None
        
        return safe_player, status
        
    except Exception as e:
        # Fallback completo em caso de erro inesperado
        app.logger.warning(f"Error processing player {player_id}: {str(e)}")
        return {
            'full_name': f'Player_{player_id[:6]}',
            'position': '?',
            'team': '?',
            'injury_status': 'Unknown'
        }, 'Unknown'

def get_starters_with_status(user_id, force_refresh=False):
    """Obtém starters com status usando paralelização"""
    try:
        if force_refresh:
            LEAGUE_CACHE.clear()
            
        leagues = get_cached_leagues(user_id)
        all_players = get_all_players()
        leagues_data = {}
        
        for league in leagues:
            league_id = league['league_id']
            
            # Paralelização: buscar configurações e rosters ao mesmo tempo
            with ThreadPoolExecutor() as executor:
                settings_future = executor.submit(get_league_settings, league_id)
                rosters_future = executor.submit(get_cached_rosters, league_id)
                league_settings = settings_future.result()
                rosters = rosters_future.result()
            
            if not league_settings or not rosters:
                continue
                
            roster_positions = league_settings.get('roster_positions', [])
            league_issues = []
            total_issues = 0
            
            user_rosters = [r for r in rosters if r.get('owner_id') == user_id]
            
            for roster in user_rosters:
                starters = roster.get('starters', []) or []
                
                empty_positions = _process_empty_positions(starters, roster_positions)
                if empty_positions:
                    league_issues.append({
                        'status': 'Empty Position',
                        'positions': empty_positions,
                        'count': len(empty_positions),
                        'is_empty': True
                    })
                    total_issues += len(empty_positions)
                
                status_groups = {}
                for player_id in starters:
                    player, status = _process_player_status(player_id, all_players)
                    if not status:
                        continue
                    
                    if status not in status_groups:
                        status_groups[status] = []
                    
                    status_groups[status].append({
                        'id': player_id,
                        'name': player.get('full_name', f'Unknown Player ({player_id})'),
                        'position': player.get('position', '?'),
                        'team': player.get('team', '?'),
                        'status': status
                    })
                
                for status in STATUS_CONFIG:
                    if status in status_groups:
                        league_issues.append({
                            'status': status,
                            'players': status_groups[status],
                            'count': len(status_groups[status])
                        })
                        total_issues += len(status_groups[status])
            
            if league_issues:
                leagues_data[league_id] = {
                    'name': league['name'],
                    'issues': league_issues,
                    'total_issues': total_issues
                }
        
        return leagues_data
    
    except Exception as e:
        app.logger.error(f"Error in get_starters_with_status: {str(e)}", exc_info=True)
        return {}

# ==================== DECORATORS E HELPERS ====================
def login_required(f):
    """Decorator para rotas que requerem login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.accept_mimetypes.accept_json:
                return jsonify({'error': 'Unauthorized'}), 401
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# Adicionar CSP headers para segurança
@app.after_request
def add_csp(response):
    csp = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https://sleeper.com;"
    response.headers['Content-Security-Policy'] = csp
    return response

# ==================== ROTAS ====================
@app.route('/login', methods=['POST'])
def login():
    """Realiza o login do usuário"""
    data = request.get_json()
    username = data.get('username')
    
    if not username:
        return jsonify({
            'success': False,
            'message': 'Please insert your Sleeper user'
        }), 400
    
    user_id = get_user_id(username)
    if user_id:
        session['user_id'] = user_id
        session['username'] = username
        return jsonify({'success': True})
    
    return jsonify({
        'success': False,
        'message': 'User not found, please check the login and try again'
    }), 404

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/check-login')
def check_login():
    """Verifica se o usuário está logado"""
    return jsonify({'logged_in': 'user_id' in session, 'username': session.get('username', '')})

@app.route('/', methods=['GET', 'POST'])
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form['username']
        user_id = get_user_id(username)
        if user_id:
            session['user_id'] = user_id
            session['username'] = username
            return redirect(url_for('dashboard'))
        else:
            return render_template('index.html', error='User not found, please check the login and try again')
    
    return render_template('index.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', username=session['username'])

@app.route('/api/refresh-players-cache')
@login_required
def refresh_players_cache():
    """Força a atualização do cache de jogadores"""
    try:
        # Busca novos dados da API
        players = sleeper_request(f'https://api.sleeper.app/v1/players/{SPORT}', timeout=15)
        
        if not players:
            return jsonify({'success': False, 'message': 'Failed to fetch players'}), 500
            
        # Filtra ativos e salva
        active_players = {
            player_id: player_data
            for player_id, player_data in players.items()
            if player_data.get('active') is True
        }
        
        # Atualiza caches
        PLAYERS_CACHE['data'] = active_players
        save_players_to_disk(active_players)
        
        return jsonify({
            'success': True,
            'message': f'Cache atualizado com {len(active_players)} jogadores'
        })
        
    except Exception as e:
        app.logger.error(f"Erro ao atualizar cache: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'message': 'Erro interno ao atualizar cache'
        }), 500

@app.route('/league/<league_id>')
@login_required
def league(league_id):
    if not league_id.isdigit():
        return render_template('error.html', error="Invalid league ID"), 400
    
    data = get_league_data(league_id, ['league', 'rosters', 'users'])
    
    if not data.get('league'):
        return render_template('error.html', error="League not found"), 404
    
    for roster in data['rosters']:
        owner = next((u for u in data['users'] if u['user_id'] == roster['owner_id']), {})
        roster['owner'] = owner
    
    return render_template('league.html', 
                          league=data['league'], 
                          rosters=data['rosters'],
                          current_week=1)

@app.route('/api/player-status')
@login_required
def player_status():
    """Endpoint para obter dados de status dos jogadores (cache normal)"""
    try:
        user_id = session['user_id']
        #season = request.args.get('season', CURRENT_SEASON, type=int)
        status_data = get_starters_with_status(user_id)
        return jsonify(status_data)
    except Exception as e:
        app.logger.error(f"Error in player_status endpoint: {str(e)}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/refresh-league-status')
@login_required
def refresh_league_status():
    """Endpoint para forçar atualização das ligas e rosters"""
    try:
        user_id = session['user_id']
        #season = request.args.get('season', CURRENT_SEASON, type=int)
        status_data = get_starters_with_status(user_id, force_refresh=True)
        return jsonify(status_data)
    except Exception as e:
        app.logger.error(f"Error refreshing league status: {str(e)}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/cache-info')
@login_required
def cache_info():
    """Retorna informações sobre o estado do cache"""
    try:
        if os.path.exists(PLAYERS_CACHE_FILE):
            mod_time = os.path.getmtime(PLAYERS_CACHE_FILE)
            mod_datetime = datetime.fromtimestamp(mod_time)
            ttl = get_cache_ttl()
            expires_at = datetime.fromtimestamp(mod_time + ttl)
            
            return jsonify({
                'last_updated': mod_datetime.isoformat(),
                'expires_at': expires_at.isoformat(),
                'ttl_seconds': ttl,
                'cache_size': os.path.getsize(PLAYERS_CACHE_FILE),
                'is_night': is_night_time(),
                'is_morning': is_morning_time()
            })
        return jsonify({'status': 'no_cache'})
    except Exception as e:
        app.logger.error(f"Error getting cache info: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/top-players')
@login_required
def top_players():
    try:
        user_id = session['user_id']
        #season = request.args.get('season', CURRENT_SEASON, type=int)
        leagues = get_cached_leagues(user_id) or []
        all_players_data = get_all_players() or {}
        
        if not leagues or not all_players_data:
            return jsonify([])
        
        player_map = {}
        
        for league in leagues:
            if not league or 'league_id' not in league:
                continue
                
            league_id = league['league_id']
            rosters = get_cached_rosters(league_id) or []
            
            # Filtra rosters válidos do usuário
            user_rosters = [
                r for r in rosters 
                if r and isinstance(r, dict) and r.get('owner_id') == user_id
            ]
            
            for roster in user_rosters:
                players_list = roster.get('players') or []
                
                for player_id in players_list:
                    if not player_id or player_id in ['', '0', 'None']:
                        continue
                    
                    # Obter dados do jogador com fallbacks
                    player_data = all_players_data.get(player_id, {})
                    full_name = player_data.get('full_name') or f'Player_{player_id[:6]}'
                    
                    # Se é a primeira vez que vemos este player_id
                    if player_id not in player_map:
                        # Obter status com valor padrão
                        injury_status = player_data.get('injury_status') or 'Active'
                        injury_status = format_status(injury_status)
                        
                        player_map[player_id] = {
                            'name': full_name,
                            'count': 0,
                            'leagues': [],
                            'position': player_data.get('position', '?'),
                            'injury_status': injury_status
                        }
                    
                    # Incrementar contagem de ocorrências
                    player_map[player_id]['count'] += 1
                    
                    # Obter posição no roster
                    try:
                        roster_position = get_roster_position(player_id, roster, league_id)
                    except Exception as e:
                        app.logger.warning(f"Error getting roster position for {player_id}: {str(e)}")
                        roster_position = "BN"
                    
                    # Adicionar detalhes da liga
                    player_map[player_id]['leagues'].append({
                        'league_name': league.get('name', 'Unknown League'),
                        'league_id': league_id,
                        'roster_id': roster.get('roster_id', 'unknown'),
                        'roster_position': roster_position
                    })
        
        if not player_map:
            return jsonify([])
        
        # Converter para lista e ordenar
        players_list = list(player_map.values())
        players_list.sort(key=lambda x: (-x['count'], x['name']))
        
        # Retornar apenas os TOPN
        return jsonify(players_list[:TOPN])
    
    except Exception as e:
        app.logger.error(f"Error in top_players: {str(e)}", exc_info=True)
        return jsonify([])

# Função auxiliar para determinar a posição no roster (mantida igual)
def get_roster_position(player_id, roster, league_id):
    """Determina a posição do jogador no roster com base nas novas regras"""
    # Trata campos que podem ser None
    reserve = roster.get('reserve') or []
    starters = roster.get('starters') or []
    taxi = roster.get('taxi') or []
    
    if player_id in reserve:
        return "IR"
    elif player_id in starters:
        try:
            # Tentar obter posição exata
            idx = starters.index(player_id)
            roster_positions = get_league_settings(league_id).get('roster_positions', [])
            return roster_positions[idx] if idx < len(roster_positions) else "ST"
        except:
            return "ST"
    elif player_id in taxi:
        return "TS"
    else:
        return "BN"

@app.route('/api/search-players')
@login_required
def search_players():
    try:
        query = request.args.get('query', '').strip().lower()[:50]
        positions = request.args.getlist('positions')
        
        if not positions:
            return jsonify([])
        
        all_players = get_all_players()
        if not all_players:
            return jsonify({'error': 'Failed to load player data'}), 500
        
        results = []
        
        for player_id, player in all_players.items():
            full_name = player.get('full_name', '').lower()
            if not full_name:
                continue
                
            player_positions = player.get('fantasy_positions', []) or []
            
            if not player_positions or not isinstance(player_positions, list):
                continue

            if not any(pos in positions for pos in player_positions):
                continue
            
            if query and query not in full_name:
                continue
            
            status = player.get('status', 'Active')
            status_abbr = STATUS_CONFIG.get(status, {}).get('abbr', '')
            
            results.append({
                'id': player_id,
                'name': player.get('full_name', 'Unknown Player'),
                'positions': player_positions,
                'status': status,
                'status_abbr': status_abbr
            })
        
        results.sort(key=lambda x: x['name'])
        return jsonify(results)
    
    except Exception as e:
        app.logger.error(f"Error in search_players: {str(e)}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500

def format_status(status):
    """Formata o status para um padrão consistente: primeira letra maiúscula, resto minúscula"""
    if not status:
        return 'Active'
    
    status = status.strip()
    status_lower = status.lower()
    
    # Mapeia siglas para nomes completos
    status_map = {
        'pup': 'PUP',
        'ir': 'IR',
        's': 'Suspended',
        'o': 'Out',
        'd': 'Doubtful',
        'q': 'Questionable',
        'p': 'Probable',
        'active': 'Active'
    }
    
    # Verifica se é uma sigla conhecida
    if status_lower in status_map:
        return status_map[status_lower]
    
    # Capitaliza palavras completas
    return status.capitalize()

@app.route('/api/player-details')
@login_required
def player_details():
    try:
        # Obter parâmetros com validação reforçada
        player_name = request.args.get('name', '').strip()
        if not player_name or len(player_name) < 2:
            return jsonify({'error': 'Invalid player name'}), 400
            
        #season = request.args.get('season', CURRENT_SEASON, type=int)
        user_id = session['user_id']
        
        # Buscar ligas e jogadores com tratamento de null
        leagues = get_cached_leagues(user_id) or []
        all_players = get_all_players() or {}
        
        if not leagues or not all_players:
            return jsonify({'error': 'No data available'}), 404
        
        # Encontrar jogador pelo nome com fallback robusto
        player_id = None
        player_data = None
        
        for pid, pdata in all_players.items():
            full_name = pdata.get('full_name', '').strip()
            if not full_name:
                continue
                
            if full_name.lower() == player_name.lower():
                player_id = pid
                player_data = pdata
                break
        
        if not player_id or not player_data:
            return jsonify({'error': 'Player not found'}), 404
        
        # Processar status do jogador com formatação consistente
        natural_position = player_data.get('position', '?')
        raw_status = player_data.get('injury_status') or player_data.get('status') or 'Active'
        natural_status = format_status(raw_status)
        
        # Buscar em todas as ligas do usuário com tratamento seguro
        leagues_with_player = []
        
        for league in leagues:
            if not league:
                continue
                
            league_id = league.get('league_id')
            if not league_id:
                continue
                
            rosters = get_cached_rosters(league_id) or []
            
            for roster in rosters:
                if not roster or roster.get('owner_id') != user_id:
                    continue
                    
                players_list = roster.get('players', []) or []
                
                if player_id in players_list:
                    try:
                        roster_position = get_roster_position(player_id, roster, league_id)
                    except Exception as e:
                        app.logger.warning(f"Error getting roster position: {str(e)}")
                        roster_position = "BN"
                    
                    leagues_with_player.append({
                        'league_id': league_id,
                        'league_name': league.get('name', 'Unknown League'),
                        'roster_position': roster_position,
                        'roster_id': roster.get('roster_id', 'unknown')
                    })
                    break  # Parar após encontrar em um roster
        
        return jsonify({
            'player_name': player_name,
            'position': natural_position,
            'injury_status': natural_status,
            'leagues': leagues_with_player
        })
        
    except Exception as e:
        app.logger.error(f"Error in player_details: {str(e)}", exc_info=True)
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500

@app.errorhandler(Exception)
def handle_global_errors(e):
    app.logger.error(f"Global error: {str(e)}", exc_info=True)
    return jsonify({
        'error': 'Internal server error',
        'message': 'An unexpected error occurred'
    }), 500

@app.route('/favicon.ico')
def favicon():
    return '', 204

def get_league_data(league_id, components):
    """Obtém dados específicos da liga"""
    data = {}
    endpoints = {
        'league': f'https://api.sleeper.app/v1/league/{league_id}',
        'rosters': f'https://api.sleeper.app/v1/league/{league_id}/rosters',
        'users': f'https://api.sleeper.app/v1/league/{league_id}/users',
    }
    
    for comp in components:
        if comp in endpoints:
            data[comp] = sleeper_request(endpoints[comp]) or []
    
    return data
    
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)