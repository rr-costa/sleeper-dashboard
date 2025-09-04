import os
import json
from flask import Blueprint, jsonify, request, session, render_template, current_app
from app.utils import admin_login_required
from collections import Counter
from datetime import datetime

admin = Blueprint('admin', __name__)

def process_access_logs(logs):
    """Processa os dados brutos de log para extrair relatórios agregados."""
    if not logs:
        return {
            'raw_logs': [], 
            'unique_by_day': [], 
            'repeated_logins': [],
            'top_access_hours': []  # Adicionado
        }

    # 1. Relatório de logins únicos por dia
    logins_by_date = {}
    for entry in logs:
        try:
            # Extrai apenas a parte da data (YYYY-MM-DD) do timestamp
            date_str = datetime.strptime(entry['timestamp'], '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')
            if date_str not in logins_by_date:
                logins_by_date[date_str] = set()
            logins_by_date[date_str].add(entry['username'])
        except (ValueError, KeyError):
            continue  # Pula entradas malformadas ou sem os campos necessários

    unique_logins_per_day = [
        {'date': date, 'unique_count': len(users)}
        for date, users in logins_by_date.items()
    ]
    # Ordena por data, da mais recente para a mais antiga
    unique_logins_per_day.sort(key=lambda x: x['date'], reverse=True)

    # 2. Relatório de logins repetidos
    username_counts = Counter(entry['username'] for entry in logs if 'username' in entry)
    repeated_logins = [
        {'username': username, 'count': count}
        for username, count in username_counts.items() if count > 1
    ]
    # Ordena por contagem, do mais frequente para o menos
    repeated_logins.sort(key=lambda x: x['count'], reverse=True)

     # --- NOVA FUNCIONALIDADE: Top 5 Horários de Acesso ---
    hour_counts = Counter()
    for entry in logs:
        try:
            hour = datetime.strptime(entry['timestamp'], '%Y-%m-%d %H:%M:%S').strftime('%H')
            hour_counts[hour] += 1
        except (ValueError, KeyError):
            continue

    top_hours = hour_counts.most_common(5)
    top_access_hours = [
        {'hour_range': f"{hour}:00 - {hour}:59", 'count': count}
        for hour, count in top_hours
    ]
    # --- FIM DA NOVA FUNCIONALIDADE ---

    # Ordena o log bruto por timestamp, do mais recente para o mais antigo
    logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

    return {
        'raw_logs': logs,
        'unique_by_day': unique_logins_per_day,
        'repeated_logins': repeated_logins,
        'top_access_hours': top_access_hours # Retorna os novos dados
    }


@admin.route('/')
def admin_page():
    return render_template('admin.html')

@admin.route('/loginadmin', methods=['POST'])
def admin_login():
    data = request.get_json()
    username, password = data.get('username'), data.get('password')
    creds = current_app.config['ADMIN_CREDENTIALS']

    if not username or not password:
        return jsonify(success=False, message='Credenciais necessárias'), 400
    
    if username == creds['username'] and password == creds['password']:
        session['admin_logged_in'] = True
        session.permanent = True
        return jsonify(success=True)
    
    return jsonify(success=False, message='Credenciais inválidas'), 401

@admin.route('/access-log')
@admin_login_required
def get_access_log():
    access_log_file = current_app.config['ACCESS_LOG_FILE']
    try:
        if os.path.exists(access_log_file):
            with open(access_log_file, 'r', encoding='utf-8') as f:
                logs = json.load(f)
            processed_data = process_access_logs(logs)
            return jsonify(processed_data)

        # Retorna uma estrutura vazia se o arquivo de log não existir
        return jsonify(process_access_logs([]))
    except Exception as e:
        current_app.logger.error(f"Erro ao ler e processar log de acessos: {str(e)}")
        return jsonify(error='Erro ao carregar dados'), 500

@admin.route('/clear-log', methods=['POST'])
@admin_login_required
def clear_access_log():
    access_log_file = current_app.config['ACCESS_LOG_FILE']
    try:
        if os.path.exists(access_log_file):
            os.remove(access_log_file)
        return jsonify(success=True)
    except Exception as e:
        current_app.logger.error(f"Erro ao limpar log: {str(e)}")
        return jsonify(error='Erro ao limpar log'), 500

@admin.route('/logout')
@admin_login_required
def admin_logout():
    session.pop('admin_logged_in', None)
    return jsonify(success=True)