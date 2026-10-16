"""Replays do AWBW → JSON simples para o awbw4 (scripts/train/replays.ts). Só muda o formato.
Uso: python -I exportar_replays.py <catalogo.csv> <pasta dos replays> <saída.jsonl.gz> [ligas] [tiers]"""
import csv, glob, gzip, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from awbw_replay import read_replay

cat, src, out = sys.argv[1], sys.argv[2], sys.argv[3]
leagues = (sys.argv[4] if len(sys.argv) > 4 else 'STD').split(',')
tiers = sys.argv[5] if len(sys.argv) > 5 else '1234'
rows = [r for r in csv.DictReader(open(cat, encoding='utf-8')) if r['liga'] in leagues and r['tier'] in tiers and r['jogadores'] == '2']
paths = {}
for p in glob.glob(os.path.join(src, '**', '*.zip'), recursive=True):
    b = os.path.basename(p)
    paths[b.split('_')[1] if b.startswith('replay_') else b.split('.')[0]] = p


def g(view, player=None):
    """A vista de uma unidade/caminho: a "global" (sem nevoeiro) ou a de quem joga (com nevoeiro)."""
    if not isinstance(view, dict):
        return view
    if 'global' in view:
        return view['global']
    if player is not None and str(player) in view:
        return view[str(player)]
    return next(iter(view.values()), None)


def unit_of(a, player=None):
    u = g(a.get('unit') or a.get('newUnit') or {}, player)
    return u if isinstance(u, dict) else {}


def state(s):
    return {
        'day': s['day'], 'turn': s['turn'],
        'players': [{'id': p['id'], 'funds': p['funds'], 'power': p['co_power'], 'on': p['co_power_on'], 'eliminated': p['eliminated']} for p in s['players'].values()],
        'units': [{'id': u['id'], 'player': u['players_id'], 'name': u['name'], 'x': u['x'], 'y': u['y'], 'hp': u['hit_points'],
                   'fuel': u['fuel'], 'ammo': u['ammo'], 'carried': u['carried'], 'cargo': [c for c in (u['cargo1_units_id'], u['cargo2_units_id']) if c],
                   'moved': u['moved']} for u in s['units'].values()],
        'buildings': [{'x': b['x'], 'y': b['y'], 't': b['terrain_id'], 'cap': b['capture']} for b in s['buildings'].values()],
    }


def action(a, player=None):
    k = a.get('action')
    mv = a.get('Move') if isinstance(a.get('Move'), dict) else (a if k == 'Move' else None)
    out = {'k': k}
    if mv:
        u = unit_of(mv, player)
        path = g(mv.get('paths') or {}, player) or []
        out.update({'unit': u.get('units_id'), 'path': [[p['x'], p['y']] for p in path], 'trapped': bool(mv.get('trapped'))})
    if k == 'Fire':
        ci = (g((a.get('Fire') or {}).get('combatInfoVision') or {}, player) or {}).get('combatInfo') or {}
        att = ci.get('attacker') if isinstance(ci.get('attacker'), dict) else {}
        dfn = ci.get('defender') if isinstance(ci.get('defender'), dict) else {}
        out.update({'attacker': att.get('units_id'), 'target': dfn.get('units_id'), 'hpA': att.get('units_hit_points'), 'hpD': dfn.get('units_hit_points')})
    elif k == 'Capt':
        bi = (a.get('Capt') or {}).get('buildingInfo') or {}
        out.update({'cap': bi.get('buildings_capture'), 'bx': bi.get('buildings_x'), 'by': bi.get('buildings_y')})
    elif k == 'Build':
        u = unit_of(a, player)
        out.update({'unit': u.get('units_id'), 'name': u.get('units_name'), 'x': u.get('units_x'), 'y': u.get('units_y')})
    elif k == 'Unload':
        u = unit_of(a, player)
        out.update({'unit': u.get('units_id'), 'transport': a.get('transportID'), 'x': u.get('units_x'), 'y': u.get('units_y')})
    elif k == 'Power':
        out.update({'player': a.get('playerID'), 'super': a.get('coPower') == 'S', 'name': a.get('powerName')})
    elif k == 'Join':
        jn = a.get('Join') or {}
        out.update({'target': jn.get('joinID') or jn.get('units_id')})
    return out


n = 0
with gzip.open(out, 'wt', encoding='utf-8') as f:
    for r in rows:
        p = paths.get(r['id'])
        if not p:
            continue
        states, turns = read_replay(p)
        g0 = states[0]
        f.write(json.dumps({
            'id': g0['id'], 'name': g0['name'], 'map': g0['maps_id'], 'tier': r['tier'], 'league': r['liga'], 'fog': g0['fog'] == 'Y',
            'players': [{'id': q['id'], 'country': q['countries_id'], 'co': q['co_image'].replace('.png', ''), 'order': q['order']} for q in g0['players'].values()],
            'winner': r['vencedor_ordem'], 'end': r['fim'],
            'states': [state(s) for s in states],
            'turns': [{'player': t['player'], 'day': t['day'], 'actions': [action(a, t['player']) for a in t['actions']]} for t in turns],
        }, separators=(',', ':')) + '\n')
        n += 1
print(f'{n} jogos -> {out}')
