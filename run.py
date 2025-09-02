import os
from app import create_app

# Cria a aplicação usando a fábrica a partir da configuração do ambiente
app = create_app(os.getenv('FLASK_CONFIG') or 'default')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    # O modo debug será controlado pela variável de ambiente FLASK_ENV
    app.run(host='0.0.0.0', port=port)