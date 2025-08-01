from flask import Flask, render_template, request, session, redirect, url_for, jsonify
import requests
import os
import logging
from datetime import datetime, timedelta
from functools import wraps
from dotenv import load_dotenv

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
#LOG
if os.getenv('FLASK_ENV') == 'development':
    app.logger.setLevel(logging.INFO)
    logging.getLogger().setLevel(logging.INFO)
else:
    app.logger.setLevel(logging.WARNING)
    logging.getLogger().setLevel(logging.WARNING)

# Configurações
SPORT = 'nfl'
CURRENT_SEASON = datetime.now().year
season = CURRENT_SEASON  # Temporada atual, pode ser alterada dinamicamente
TOPN = 5  # Número de jogadores a serem retornados nas listas

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

# Cache de jogadores
PLAYERS_CACHE = {
    'data': None,
    'timestamp': None,
    'expiry': 600  # 10 minutos em segundos
}

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
    """Obtém todos os jogadores ativos da NFL com cache de 10 minutos"""
    current_time = datetime.now()
    
    # Verifica se o cache é válido
    if PLAYERS_CACHE['data'] is not None:
        age = (current_time - PLAYERS_CACHE['timestamp']).total_seconds()
        #app.logger.info(f"Cache disponível - idade: {age:.1f}s")
        if age < PLAYERS_CACHE['expiry']:
            #app.logger.info(f"Retornando cache ({len(PLAYERS_CACHE['data'])} jogadores)")
            return PLAYERS_CACHE['data']
    
    try:
        #app.logger.info("Buscando jogadores da API Sleeper...")
        players = sleeper_request(f'https://api.sleeper.app/v1/players/{SPORT}', timeout=15)
        
        if not players:
            app.logger.warning("Resposta vazia da API de jogadores")
            return PLAYERS_CACHE['data'] or {}
            
        #app.logger.info(f"Total de jogadores recebidos: {len(players)}")
        #app.logger.info(f"jogadores recebidos: {(players)}")

        active_players = {}
        active_count = 0
        inactive_reasons = {
            'active_false': 0,
            'status_inactive': 0,
            'no_team': 0
        }
        
        for player_id, player_data in players.items():
            # Critério 1: Campo 'active' deve ser True
            if player_data.get('active') is not True:
                inactive_reasons['active_false'] += 1
                continue
                
            # Critério 2: Status não deve ser 'Retired' ou 'Inactive'
            #if player_data.get('status') in ['Retired', 'Inactive']:
            #    inactive_reasons['status_inactive'] += 1
            #    continue
                
            # Critério 3: Deve pertencer a um time (não ser null)
            #if player_data.get('team') is None:
            #    inactive_reasons['no_team'] += 1
            #    continue
                
            active_players[player_id] = player_data
            active_count += 1
        
        #app.logger.info(f"Jogadores ativos filtrados: {active_count}")
        #app.logger.info(f"Razões de inatividade: {inactive_reasons}")
        
        # Log de exemplo
        if active_count > 0:
            sample_player = next(iter(active_players.values()))
            #app.logger.info(f"Exemplo de jogador ativo: {sample_player.get('full_name')} - Team: {sample_player.get('team')}")
        
        PLAYERS_CACHE['data'] = active_players
        PLAYERS_CACHE['timestamp'] = current_time
        
        return active_players
        
    except Exception as e:
        app.logger.error(f"Erro ao buscar jogadores: {str(e)}", exc_info=True)
        return PLAYERS_CACHE['data'] or {}
    
def get_user_id(username):
    """Obtém o ID do usuário pelo username do Sleeper"""
    user_data = sleeper_request(f'https://api.sleeper.app/v1/user/{username}', timeout=5)
    return user_data.get('user_id') if user_data else None

def get_user_leagues(user_id, season):
    """Obtém todas as ligas do usuário na temporada atual"""
    return sleeper_request(f'https://api.sleeper.app/v1/user/{user_id}/leagues/nfl/{season}', timeout=10) or []

def get_rosters(league_id, user_id=None):
    """Obtém rosters da liga, opcionalmente filtrando por user_id"""
    rosters = sleeper_request(f'https://api.sleeper.app/v1/league/{league_id}/rosters') or []
    return [r for r in rosters if not user_id or r['owner_id'] == user_id]

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

# ==================== PROCESSAMENTO DE STATUS ====================
def _process_empty_positions(starters, roster_positions):
    """Identifica posições vazias no lineup usando nomes reais"""
    empty = []
    for i, player_id in enumerate(starters):
        if not player_id or player_id in ['None', '0']:
            # Usar a posição real se disponível, senão manter o formato antigo
            position_name = roster_positions[i] if i < len(roster_positions) else f"Position {i+1}"
            empty.append(position_name)
    return empty

def _process_player_status(player_id, all_players):
    """Processa status de um jogador individual"""
    if not player_id or player_id in ['None', '0', '']:
        return None, None
    
    player = all_players.get(player_id)
    if not player:
        app.logger.warning(f"Player not found: {player_id}")
        return None, None
    
    status = player.get('injury_status', 'Active')
    return player, status if status != 'Active' else None

def get_starters_with_status(user_id, season):
    try:
        leagues = get_user_leagues(user_id, season)
        all_players = get_all_players()
        leagues_data = {}
        
        for league in leagues:
            league_id = league['league_id']
            # Obter configurações da liga para pegar as posições
            league_settings = get_league_settings(league_id)
            if not league_settings:
                continue
                
            roster_positions = league_settings.get('roster_positions', [])
            
            rosters = get_rosters(league_id, user_id)
            
            league_issues = []
            total_issues = 0
            
            for roster in rosters:
                starters = roster.get('starters', []) or []
                
                # Passar roster_positions para a função
                empty_positions = _process_empty_positions(starters, roster_positions)
                if empty_positions:
                    league_issues.append({
                        'status': 'Empty Position',
                        'positions': empty_positions,
                        'count': len(empty_positions),
                        'is_empty': True
                    })
                    total_issues += len(empty_positions)
                
                # Verificar status dos jogadores
                status_groups = {}
                for player_id in starters:
                    player, status = _process_player_status(player_id, all_players)
                    if not status:
                        continue
                    
                    if status not in status_groups:
                        status_groups[status] = []
                    
                    status_groups[status].append({
                        'id': player_id,
                        'name': player.get('full_name', f'Unknown Player ({player_id})') if player else f'Unknown Player ({player_id})',
                        'position': player.get('position', '?') if player else '?',
                        'team': player.get('team', '?') if player else '?',
                        'status': status
                    })
                
                # Adicionar na ordem correta
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


def get_league_settings(league_id):
    """Obtém as configurações da liga incluindo as posições do roster"""
    return sleeper_request(f'https://api.sleeper.app/v1/league/{league_id}')

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
    # Se já estiver logado, redireciona para dashboard
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
    """Página de detalhes da liga"""
    if not league_id.isdigit():
        return render_template('error.html', error="Invalid league ID"), 400
    
    # Obter dados da liga
    data = get_league_data(league_id, ['league', 'rosters', 'users'])
    
    if not data.get('league'):
        return render_template('error.html', error="League not found"), 404
    
    # Mapear owners para rosters
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
    """Endpoint para obter dados de status dos jogadores"""
    try:
        user_id = session['user_id']
        season = request.args.get('season', CURRENT_SEASON, type=int)
        
        status_data = get_starters_with_status(user_id, season)
        
        return jsonify(status_data)
    except Exception as e:
        app.logger.error(f"Error in player_status endpoint: {str(e)}", exc_info=True)
        
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/top-players')
@login_required
def top_players():
    """Retorna os top TOPN jogadores do usuário"""
    try:
        user_id = session['user_id']
        season = request.args.get('season', CURRENT_SEASON, type=int)
        leagues = get_user_leagues(user_id, season)
        all_players = get_all_players()
        
        if not leagues or not all_players:
            return jsonify([])
        
        player_counter = {}
        player_leagues = {}
        player_status = {}
        
        for league in leagues:
            league_id = league['league_id']
            rosters = get_rosters(league_id, user_id)
            
            for roster in rosters:
                players_list = roster.get('players', []) or []
                for player_id in players_list:
                    if not player_id:
                        continue
                    
                    player = all_players.get(player_id, {})
                    full_name = player.get('full_name', f'Player_{player_id[:TOPN]}')
                    
                    if full_name not in player_counter:
                        player_counter[full_name] = 0
                        player_status[full_name] = player.get('status', 'Active')
                        player_leagues[full_name] = []
                    
                    player_counter[full_name] += 1
                    player_leagues[full_name].append({
                        'league_name': league['name'],
                        'league_id': league_id,
                        'roster_id': roster.get('roster_id', 'unknown'),
                        'position': player.get('position', '?')
                    })
        
        if not player_counter:
            return jsonify([])
        
        # Ordena por quantidade de ligas (decrescente) e nome (crescente)
        sorted_players = sorted(player_counter.items(), key=lambda x: (-x[1], x[0]))
        top_players = [{
            'name': player,
            'count': count,
            'status': player_status[player],
            'leagues': player_leagues[player]
        } for player, count in sorted_players[:TOPN]]
        
        return jsonify(top_players)
    
    except Exception as e:
        app.logger.error(f"Error in top_players: {str(e)}", exc_info=True)
        return jsonify([])

@app.route('/api/search-players')
@login_required
def search_players():
    """Busca jogadores com base em query e posições selecionadas"""
    try:
        query = request.args.get('query', '').strip().lower()[:50]
        positions = request.args.getlist('positions')
        
        # Se não houver posições selecionadas, retorna array vazio
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
            
            # Verificar se o jogador tem posições válidas
            if not player_positions or not isinstance(player_positions, list):
                continue

            # Verifica se o jogador tem pelo menos uma posição nas selecionadas
            if not any(pos in positions for pos in player_positions):
                continue
            
            # Verifica se o nome contém a query
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
        
        # Ordena por nome
        results.sort(key=lambda x: x['name'])
        return jsonify(results[:10])
    
    except Exception as e:
        app.logger.error(f"Error in search_players: {str(e)}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/available-years')
@login_required
def available_years():
    """Retorna os anos disponíveis para seleção"""
    current_year = datetime.now().year
    years = list(range(2023, current_year + 1))  # De 2023 até o ano atual
    return jsonify(years)

# ==================== TRATAMENTO DE ERROS GLOBAL ====================
@app.errorhandler(Exception)
def handle_global_errors(e):
    app.logger.error(f"Global error: {str(e)}", exc_info=True)
    return jsonify({
        'error': 'Internal server error',
        'message': 'An unexpected error occurred'
    }), 500

# ==================== ROTA FAVICON ====================
@app.route('/favicon.ico')
def favicon():
    return '', 204  # Retorna uma resposta vazia com status 204 (No Content)

@app.route('/api/player-details')
@login_required
def player_details():
    """Endpoint para obter detalhes do jogador em todas as ligas"""
    try:
        player_name = request.args.get('name', '').strip()
        season = request.args.get('season', CURRENT_SEASON, type=int)
        user_id = session['user_id']
        
        if not player_name:
            return jsonify({'error': 'Player name is required'}), 400
        
        # Obter todas as ligas do usuário
        leagues = get_user_leagues(user_id, season)
        all_players = get_all_players()
        
        if not leagues or not all_players:
            return jsonify({'error': 'No data available'}), 404
        
        # Encontrar o ID do jogador pelo nome
        player_id = None
        for pid, player in all_players.items():
            if player.get('full_name', '').lower() == player_name.lower():
                player_id = pid
                break
        
        if not player_id:
            return jsonify({'error': 'Player not found'}), 404
        
        player_data = all_players.get(player_id, {})
        leagues_with_player = []
        
        # Verificar em quais ligas o jogador está (APENAS NAS DO USUÁRIO)
        for league in leagues:
            league_id = league['league_id']
            rosters = get_rosters(league_id, user_id) or []  # FILTRA APENAS ROSTERS DO USUÁRIO
            
            for roster in rosters:
                players_list = roster.get('players') or []
                
                if player_id in players_list:
                    position = player_data.get('position', '?')
                    status = player_data.get('injury_status', 'Active')
                    status_abbr = STATUS_CONFIG.get(status, {}).get('abbr', '')
                    
                    leagues_with_player.append({
                        'league_id': league_id,
                        'league_name': league['name'],
                        'position': position,
                        'status': status,
                        'status_abbr': status_abbr,
                        'roster_id': roster.get('roster_id', 'unknown')
                    })
                    break  # Jogador só pode estar em um roster por liga
        
        return jsonify({
            'player_name': player_name,
            'leagues': leagues_with_player
        })
        
    except Exception as e:
        app.logger.error(f"Error in player_details: {str(e)}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500
    
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)