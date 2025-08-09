from flask import Flask, render_template, request, session, redirect, url_for, jsonify
import requests
import os
import logging
from datetime import datetime, timedelta
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
CURRENT_SEASON = datetime.now().year
TOPN = 6

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
    """Obtém todos os jogadores ativos da NFL com cache TTLCache"""
    try:
        # Verifica se está no cache
        if 'data' in PLAYERS_CACHE:
            return PLAYERS_CACHE['data']
        
        players = sleeper_request(f'https://api.sleeper.app/v1/players/{SPORT}', timeout=15)
        
        if not players:
            app.logger.warning("Resposta vazia da API de jogadores")
            return {}
            
        active_players = {}
        for player_id, player_data in players.items():
            if player_data.get('active') is True:
                active_players[player_id] = player_data
        
        PLAYERS_CACHE['data'] = active_players
        return active_players
        
    except Exception as e:
        app.logger.error(f"Erro ao buscar jogadores: {str(e)}", exc_info=True)
        return {}

def get_cached_leagues(user_id, season):
    """Obtém ligas com cache TTLCache"""
    cache_key = (user_id, season)
    if cache_key in LEAGUE_CACHE:
        return LEAGUE_CACHE[cache_key]
    
    leagues = sleeper_request(f'https://api.sleeper.app/v1/user/{user_id}/leagues/nfl/{season}', timeout=10) or []
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
    """Processa status de um jogador individual com fallback para desconhecidos"""
    if not player_id or player_id in ['None', '0', '']:
        return None, None
    
    player = all_players.get(player_id)
    if not player:
        return {
            'full_name': f'Unknown Player ({player_id})',
            'position': '?',
            'team': '?',
            'injury_status': 'Unknown'
        }, 'Unknown'
    
    status = player.get('injury_status', 'Active')
    return player, status if status != 'Active' else None

def get_starters_with_status(user_id, season, force_refresh=False):
    """Obtém starters com status usando paralelização"""
    try:
        if force_refresh:
            LEAGUE_CACHE.clear()
            
        leagues = get_cached_leagues(user_id, season)
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
        season = request.args.get('season', CURRENT_SEASON, type=int)
        status_data = get_starters_with_status(user_id, season)
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
        season = request.args.get('season', CURRENT_SEASON, type=int)
        status_data = get_starters_with_status(user_id, season, force_refresh=True)
        return jsonify(status_data)
    except Exception as e:
        app.logger.error(f"Error refreshing league status: {str(e)}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/top-players')
@login_required
def top_players():
    try:
        user_id = session['user_id']
        season = request.args.get('season', CURRENT_SEASON, type=int)
        leagues = get_cached_leagues(user_id, season)
        all_players_data = get_all_players()
        
        if not leagues or not all_players_data:
            return jsonify([])
        
        player_map = {}
        
        for league in leagues:
            league_id = league['league_id']
            rosters = get_cached_rosters(league_id) or []
            user_rosters = [r for r in rosters if r.get('owner_id') == user_id]
            
            for roster in user_rosters:
                # Garante que temos uma lista válida
                players_list = roster.get('players') or []
                
                for player_id in players_list:
                    if not player_id:
                        continue
                    
                    player_data = all_players_data.get(player_id, {})
                    full_name = player_data.get('full_name', f'Player_{player_id[:6]}')
                    
                    # Se é a primeira vez, inicializa
                    if player_id not in player_map:
                        # Obter abreviatura de status
                        injury_status = player_data.get('injury_status', 'Active')
                        status_config = STATUS_CONFIG.get(injury_status, {})
                        status_abbr = status_config.get('abbr', injury_status[:2].upper() if injury_status else 'A')
                        
                        player_map[player_id] = {
                            'name': full_name,
                            'count': 0,
                            'leagues': [],
                            'position': player_data.get('position', '?'),
                            'injury_status': injury_status,
                            'status_abbr': status_abbr
                        }
                    
                    # Incrementar contagem
                    player_map[player_id]['count'] += 1
                    
                    # Adicionar detalhes da liga
                    roster_position = get_roster_position(player_id, roster, league_id)
                    player_map[player_id]['leagues'].append({
                        'league_name': league['name'],
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

@app.route('/api/available-years')
@login_required
def available_years():
    current_year = datetime.now().year
    years = list(range(2023, current_year + 1))
    return jsonify(years)

@app.route('/api/player-details')
@login_required
def player_details():
    try:
        # Obter parâmetros da requisição com validação reforçada
        player_name = request.args.get('name', '').strip()
        if not player_name or len(player_name) < 2:
            return jsonify({'error': 'Invalid player name'}), 400
            
        season = request.args.get('season', CURRENT_SEASON, type=int)
        user_id = session['user_id']
        
        # Buscar ligas e jogadores
        leagues = get_cached_leagues(user_id, season)
        all_players = get_all_players()
        
        if not leagues or not all_players:
            return jsonify({'error': 'No data available'}), 404
        
        # Encontrar jogador pelo nome
        player_id = None
        player_data = None
        for pid, pdata in all_players.items():
            if pdata.get('full_name', '').lower() == player_name.lower():
                player_id = pid
                player_data = pdata
                break
        
        if not player_id or not player_data:
            return jsonify({'error': 'Player not found'}), 404
        
        # Processar status do jogador
        natural_position = player_data.get('position', '?')
        natural_status = player_data.get('injury_status') or player_data.get('status', 'Active')
        status_abbr = STATUS_CONFIG.get(natural_status, {}).get('abbr', natural_status[:2].upper())
        
        # Buscar em todas as ligas do usuário
        leagues_with_player = []
        
        for league in leagues:
            league_id = league['league_id']
            rosters = get_cached_rosters(league_id) or []
            user_rosters = [r for r in rosters if r.get('owner_id') == user_id]
            
            for roster in user_rosters:
                players_list = roster.get('players', [])
                
                if player_id in players_list:
                    # Determinar status do roster com base nas novas regras
                    if player_id in roster.get('reserve', []):
                        roster_position = "IR"  # Regra 1: Reserve = IR
                    elif player_id in roster.get('starters', []):
                        try:
                            # Tentar obter posição exata
                            idx = roster['starters'].index(player_id)
                            roster_positions = get_league_settings(league_id).get('roster_positions', [])
                            roster_position = roster_positions[idx] if idx < len(roster_positions) else "ST"
                        except:
                            roster_position = "ST"
                    elif player_id in roster.get('taxi', []):
                        roster_position = "TS"
                    else:
                        roster_position = "BN"  # Regra 2: Não está em starters/taxi/reserve
                    
                    leagues_with_player.append({
                        'league_id': league_id,
                        'league_name': league['name'],
                        'roster_position': roster_position,
                        'roster_id': roster.get('roster_id', 'unknown')
                    })
                    break  # Parar após encontrar em um roster
        
        return jsonify({
            'player_name': player_name,
            'position': natural_position,
            'status': natural_status,
            'status_abbr': status_abbr,
            'leagues': leagues_with_player
        })
        
    except Exception as e:
        app.logger.error(f"Error in player_details: {str(e)}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500

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