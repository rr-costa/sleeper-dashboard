import os
import logging
from flask import Flask, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
from .config import config

def create_app(config_name):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    logging.basicConfig(level=logging.INFO)

    # Garante que o diretório de cache existe
    if not os.path.exists(app.config['CACHE_DIR']):
        os.makedirs(app.config['CACHE_DIR'])

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

    # Registrar Blueprints
    from .main.routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from .api.routes import api as api_blueprint
    app.register_blueprint(api_blueprint, url_prefix='/api')

    from .admin.routes import admin as admin_blueprint
    app.register_blueprint(admin_blueprint, url_prefix='/admin')

    # Registrar handlers de erro e hooks globais
    @app.errorhandler(Exception)
    def handle_global_errors(e):
        app.logger.error(f"Global error: {str(e)}", exc_info=True)
        return jsonify(error='Internal server error', message='An unexpected error occurred'), 500

    @app.after_request
    def add_csp(response):
        csp = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https://sleeper.com; connect-src 'self' https://ko-fi.com;"
        response.headers['Content-Security-Policy'] = csp
        return response

    return app