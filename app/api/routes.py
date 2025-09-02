import os
from flask import Blueprint, jsonify, session, request, current_app
from app import services, utils

api = Blueprint('api', __name__)

@api.route('/player-status')
@utils.login_required
def player_status():
    user_id = session['user_id']
    status_data = services.get_starters_with_status(user_id)
    return jsonify(status_data)

@api.route('/refresh-league-status')
@utils.login_required
def refresh_league_status():
    user_id = session['user_id']
    status_data = services.get_starters_with_status(user_id, force_refresh=True)
    return jsonify(status_data)

@api.route('/cache-info')
@utils.login_required
def cache_info():
    players_cache_file = current_app.config['PLAYERS_CACHE_FILE']
    if os.path.exists(players_cache_file):
        mod_time = os.path.getmtime(players_cache_file)
        ttl = utils.get_cache_ttl()
        return jsonify({
            'last_updated': datetime.fromtimestamp(mod_time).isoformat(),
            'expires_at': datetime.fromtimestamp(mod_time + ttl).isoformat(),
            'ttl_seconds': ttl,
            'cache_size': os.path.getsize(players_cache_file),
            'is_night': utils.is_night_time(),
            'is_morning': utils.is_morning_time()
        })
    return jsonify(status='no_cache')
    
@api.route('/top-players')
@utils.login_required
def top_players():
    user_id = session['user_id']
    leagues = services.get_cached_leagues(user_id) or []
    all_players_data = services.get_all_players() or {}
    player_map = {}

    for league in leagues:
        if not league or 'league_id' not in league: continue
        league_id = league['league_id']
        rosters = services.get_cached_rosters(league_id) or []
        user_rosters = [r for r in rosters if r and r.get('owner_id') == user_id]

        for roster in user_rosters:
            for player_id in roster.get('players') or []:
                if not player_id: continue
                player_data = all_players_data.get(player_id, {})
                
                if player_id not in player_map:
                    player_map[player_id] = {
                        'name': player_data.get('full_name') or f'Player_{player_id[:6]}',
                        'count': 0, 'leagues': [],
                        'position': player_data.get('position', '?'),
                        'injury_status': utils.format_status(player_data.get('injury_status') or 'Active')
                    }
                
                player_map[player_id]['count'] += 1
                roster_position = services.get_roster_position(player_id, roster, league_id)
                player_map[player_id]['leagues'].append({
                    'league_name': league.get('name', 'Unknown'), 'league_id': league_id,
                    'roster_id': roster.get('roster_id'), 'roster_position': roster_position
                })
    
    players_list = sorted(list(player_map.values()), key=lambda x: (-x['count'], x['name']))
    return jsonify(players_list[:current_app.config['TOPN']])

@api.route('/search-players')
@utils.login_required
def search_players():
    query = request.args.get('query', '').strip().lower()[:50]
    positions = request.args.getlist('positions')
    if not positions: return jsonify([])

    all_players = services.get_all_players()
    results = []
    
    for player_id, player in all_players.items():
        full_name = player.get('full_name') or f"{player.get('first_name', '')} {player.get('last_name', '')}".strip()
        if not full_name or (query and query not in full_name.lower()): continue
        
        player_positions = player.get('fantasy_positions') or []
        if not any(pos in positions for pos in player_positions): continue
        
        results.append({
            'id': player_id, 'name': full_name, 'positions': player_positions,
            'status': player.get('status', 'Active'),
            'status_abbr': current_app.config['STATUS_CONFIG'].get(player.get('status'), {}).get('abbr', ''),
            'depth_chart_order': player.get('depth_chart_order')  # Adicionar esta propriedade
        })

    # Ordenar primeiro por depth_chart_order (None vai para o final) e depois por nome
    results.sort(key=lambda x: (
        x['depth_chart_order'] if x['depth_chart_order'] is not None else float('inf'),
        x['name']
    ))
    
    return jsonify(results)

@api.route('/player-details')
@utils.login_required
def player_details():
    player_name = request.args.get('name', '').strip()
    if not player_name: return jsonify(error='Invalid player name'), 400

    user_id = session['user_id']
    leagues = services.get_cached_leagues(user_id) or []
    all_players = services.get_all_players() or {}

    player_id, player_data = None, None
    for pid, pdata in all_players.items():
        full_name = pdata.get('full_name') or f"{pdata.get('first_name', '')} {pdata.get('last_name', '')}".strip()
        if full_name.lower() == player_name.lower():
            player_id, player_data = pid, pdata
            break
    
    if not player_id: return jsonify(error='Player not found'), 404

    leagues_with_player = []
    for league in leagues:
        if not league or 'league_id' not in league: continue
        rosters = services.get_cached_rosters(league.get('league_id')) or []
        for roster in rosters:
            if roster and roster.get('owner_id') == user_id and player_id in (roster.get('players') or []):
                leagues_with_player.append({
                    'league_id': league.get('league_id'), 'league_name': league.get('name', 'Unknown'),
                    'roster_position': services.get_roster_position(player_id, roster, league.get('league_id')),
                    'roster_id': roster.get('roster_id')
                })
                break
    
    return jsonify({
        'player_name': player_name,
        'position': player_data.get('position', '?'),
        'injury_status': utils.format_status(player_data.get('injury_status') or 'Active'),
        'leagues': leagues_with_player
    })