"""Cataloga uma pasta de replays do AWBW (só lê): um CSV com mapa, regras, liga, COs, duração e fim."""
import csv, glob, os, re, sys
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from awbw_replay import read_replay

src, out = sys.argv[1], sys.argv[2]
ours = set(int(x) for x in sys.argv[3].split(',')) if len(sys.argv) > 3 else set()
rows, errors = [], Counter()
for path in sorted(glob.glob(os.path.join(src, '**', '*.zip'), recursive=True)):
    try:
        states, turns = read_replay(path)
    except Exception as e:  # formato antigo ou ficheiro estragado
        errors[type(e).__name__] += 1
        continue
    g0, gl = states[0], states[-1]
    players = sorted(g0['players'].values(), key=lambda p: p['order'])
    resign = next((t['player'] for t in turns for a in t['actions'] if a.get('action') == 'Resign'), None)
    elim = [p['id'] for p in gl['players'].values() if p.get('eliminated') == 'Y']
    loser = resign or (elim[0] if elim else None)
    winner = next((p['id'] for p in players if loser and p['id'] != loser), None) if len(players) == 2 else None
    m = re.match(r'GL (\w+) \[T(\d)\]', g0.get('name') or '')
    rows.append({
        'id': g0['id'], 'nome': g0.get('name'), 'mapa': g0['maps_id'], 'temos_mapa': int(g0['maps_id'] in ours),
        'jogadores': len(players), 'nevoeiro': g0['fog'], 'poderes': g0.get('use_powers'), 'dinheiro': g0.get('funds'),
        'liga': m.group(1) if m else '', 'tier': m.group(2) if m else '',
        'cos': '/'.join(str(p['co_id']) for p in players), 'dias': gl['day'], 'turnos': len(turns),
        'fim': 'desistencia' if resign else 'eliminado' if elim else 'sem fim', 'vencedor_ordem': next((i for i, p in enumerate(players) if p['id'] == winner), ''),
    })
with open(out, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)
print(f'{len(rows)} replays lidos, erros: {dict(errors)}')
c = Counter
print('jogadores:', dict(c(r['jogadores'] for r in rows)))
print('nevoeiro:', dict(c(r['nevoeiro'] for r in rows)))
print('liga/tier:', dict(c(f"{r['liga'] or '-'} T{r['tier'] or '-'}" for r in rows).most_common(12)))
print('dinheiro por base:', dict(c(r['dinheiro'] for r in rows).most_common(5)))
print('fim:', dict(c(r['fim'] for r in rows)))
print('em mapas que temos:', sum(r['temos_mapa'] for r in rows))
print('mapas mais jogados:', c(r['mapa'] for r in rows).most_common(15))
print('dias (mediana):', sorted(r['dias'] for r in rows)[len(rows) // 2])
