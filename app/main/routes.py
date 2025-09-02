from flask import render_template, request, session, redirect, url_for, Blueprint, jsonify
from app import services, utils

main = Blueprint('main', __name__)

@main.route('/', methods=['GET', 'POST'])
def index():
    if 'user_id' in session:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        username = request.form['username']
        user_id = services.get_user_id(username)
        if user_id:
            session['user_id'] = user_id
            session['username'] = username
            return redirect(url_for('main.dashboard'))
        else:
            return render_template('index.html', error='User not found, please check the login and try again')
    
    return render_template('index.html')

@main.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    if not username:
        return jsonify(success=False, message='Please insert your Sleeper user'), 400
    
    user_id = services.get_user_id(username)
    if user_id:
        session['user_id'], session['username'] = user_id, username
        utils.log_user_access(username)
        return jsonify(success=True)
    
    return jsonify(success=False, message='User not found, please check the login and try again'), 404

@main.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.index'))

@main.route('/check-login')
def check_login():
    return jsonify(logged_in='user_id' in session, username=session.get('username', ''))

@main.route('/dashboard')
@utils.login_required
def dashboard():
    return render_template('dashboard.html', username=session.get('username'))

@main.route('/cache')
@utils.login_required
def cache_management():
    return render_template('cache.html')

@main.route('/favicon.ico')
def favicon():
    return '', 204