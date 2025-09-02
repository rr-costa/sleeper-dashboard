import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Configuração base que outras configurações herdam."""
    SECRET_KEY = os.getenv('SECRET_KEY', 'fallback-secret-key-super-segura')
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = False  # Padrão para desenvolvimento
    PERMANENT_SESSION_LIFETIME = timedelta(hours=1)
    SESSION_REFRESH_EACH_REQUEST = True
    DEBUG = False
    
    # Configurações da aplicação
    SPORT = 'nfl'
    CURRENT_SEASON = "2025"
    TOPN = 6
    CACHE_DIR = 'cache'
    ACCESS_LOG_FILE = os.path.join(CACHE_DIR, 'access_log.json')
    PLAYERS_CACHE_FILE = os.path.join(CACHE_DIR, 'players_cache.json')

    ADMIN_CREDENTIALS = {
        'username': os.getenv('ADMIN_USERNAME'),
        'password': os.getenv('ADMIN_PASSWORD')
    }

    STATUS_CONFIG = {
        'PUP': {'order': 0, 'abbr': 'PUP'}, 'IR': {'order': 1, 'abbr': 'IR'},
        'Suspended': {'order': 2, 'abbr': 'S'}, 'OUT': {'order': 3, 'abbr': 'O'},
        'Doubtful': {'order': 4, 'abbr': 'D'}, 'Questionable': {'order': 5, 'abbr': 'Q'},
        'Probable': {'order': 6, 'abbr': 'P'}
    }
    POSITION_ORDER = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF', 'DL', 'LB', 'DB']

    @staticmethod
    def init_app(app):
        pass

class DevelopmentConfig(Config):
    """Configuração de Desenvolvimento."""
    DEBUG = True

class ProductionConfig(Config):
    """Configuração de Produção."""
    SESSION_COOKIE_SECURE = True

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}