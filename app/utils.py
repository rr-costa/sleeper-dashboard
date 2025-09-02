import os
import json
import time as time_module
from datetime import datetime, timedelta, time
from functools import wraps
from flask import session, redirect, url_for, request, jsonify, current_app
from cachetools import TTLCache

# Caches com TTLCache (in-memory)
PLAYERS_CACHE_IN_MEMORY = TTLCache(maxsize=1, ttl=600)
LEAGUE_CACHE = TTLCache(maxsize=100, ttl=300)

# --- DECORATORS ---
def login_required(f):
    """Decorator para rotas que requerem login de usuário."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.accept_mimetypes.accept_json:
                return jsonify({'error': 'Unauthorized'}), 401
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

def admin_login_required(f):
    """Decorator para rotas que requerem login de admin."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return jsonify({'error': 'Não autorizado'}), 401
        return f(*args, **kwargs)
    return decorated_function

# --- FUNÇÕES DE TEMPO E TTL ---
def is_night_time():
    now = datetime.now().time()
    return now >= time(23, 0) or now < time(6, 0)

def is_morning_time():
    now = datetime.now().time()
    return time(6, 0) <= now < time(10, 0)

def get_cache_ttl():
    if is_night_time():
        now = datetime.now()
        next_6am = (now + timedelta(days=1)).replace(hour=6, minute=0, second=0, microsecond=0)
        if now.hour >= 23:
            next_6am = now.replace(hour=6, minute=0, second=0, microsecond=0) + timedelta(days=1)
        return (next_6am - now).total_seconds()
    elif is_morning_time():
        return 3600  # 1 hora
    else:
        return 600   # 10 minutos

# --- GERENCIAMENTO DE CACHE EM DISCO ---
def load_players_from_disk():
    players_cache_file = current_app.config['PLAYERS_CACHE_FILE']
    try:
        if not os.path.exists(players_cache_file):
            return None, 0
        
        mod_time = os.path.getmtime(players_cache_file)
        current_time = time_module.time()
        
        mod_datetime = datetime.fromtimestamp(mod_time)
        mod_was_night = mod_datetime.hour >= 23 or mod_datetime.hour < 6
        
        if mod_was_night and is_night_time():
            with open(players_cache_file, 'r', encoding='utf-8') as f:
                return json.load(f), mod_time
                
        ttl = get_cache_ttl()
        if current_time - mod_time < ttl:
            with open(players_cache_file, 'r', encoding='utf-8') as f:
                return json.load(f), mod_time
                
        return None, mod_time
    except Exception as e:
        current_app.logger.error(f"Erro ao ler cache de jogadores: {str(e)}")
        return None, 0

def save_players_to_disk(players_data):
    players_cache_file = current_app.config['PLAYERS_CACHE_FILE']
    try:
        with open(players_cache_file, 'w', encoding='utf-8') as f:
            json.dump(players_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        current_app.logger.error(f"Erro ao salvar cache de jogadores: {str(e)}")
        return False

# --- LOGGING DE ACESSO ---
def log_user_access(username):
    access_log_file = current_app.config['ACCESS_LOG_FILE']
    try:
        if os.path.exists(access_log_file):
            with open(access_log_file, 'r', encoding='utf-8') as f:
                access_data = json.load(f)
        else:
            access_data = []
        
        access_data.append({
            'username': username,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'ip': request.remote_addr
        })
        
        with open(access_log_file, 'w', encoding='utf-8') as f:
            json.dump(access_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        current_app.logger.error(f"Erro ao registrar acesso: {str(e)}")

# --- FORMATAÇÃO E HELPERS ---
def format_status(status):
    if not status: return 'Active'
    status, status_lower = status.strip(), status.lower()
    status_map = {
        'pup': 'PUP', 'ir': 'IR', 's': 'Suspended', 'o': 'Out', 'd': 'Doubtful',
        'q': 'Questionable', 'p': 'Probable', 'active': 'Active'
    }
    return status_map.get(status_lower, status.capitalize())