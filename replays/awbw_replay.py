"""Leitor dos replays do AWBW (zip com dois ficheiros gzip: <id> = estados por turno, a<id> = ações).
Só lê dados: interpreta a serialização do PHP à mão (sem eval) e o JSON das ações."""
import gzip, io, json, re, sys, zipfile
from collections import Counter, defaultdict


def php_load(s, i=0):
    """Desserializa um valor PHP a partir de s[i] (bytes); devolve (valor, novo i)."""
    t = s[i:i + 1]
    if t == b'N':
        return None, i + 2
    if t in (b'i', b'b', b'd'):
        j = s.index(b';', i)
        v = s[i + 2:j].decode()
        return (int(v) if t == b'i' else v == '1' if t == b'b' else float(v)), j + 1
    if t == b's':
        j = s.index(b':', i + 2)
        n = int(s[i + 2:j])
        start = j + 2
        return s[start:start + n].decode('utf-8', errors='replace'), start + n + 2
    if t in (b'a', b'O'):
        if t == b'O':
            j = s.index(b':', i + 2)
            n = int(s[i + 2:j])
            i = j + 2 + n + 2  # nome da classe entre aspas, depois ':'
            j = s.index(b':', i)
            m = int(s[i:j])
        else:
            j = s.index(b':', i + 2)
            m = int(s[i + 2:j])
        i = j + 2
        out = {}
        for _ in range(m):
            k, i = php_load(s, i)
            v, i = php_load(s, i)
            out[k] = v
        return out, i + 1
    raise ValueError(f'tipo PHP desconhecido {t!r} em {i}')


def read_replay(path):
    z = zipfile.ZipFile(path)
    names = z.namelist()
    sname = next(n for n in names if not n.startswith('a'))
    aname = next(n for n in names if n.startswith('a'))
    states = [php_load(line)[0] for line in gzip.decompress(z.read(sname)).splitlines() if line.strip()]
    # o ficheiro das ações pode ter vários membros gzip seguidos
    raw = gzip.GzipFile(fileobj=io.BytesIO(z.read(aname))).read()
    turns = []
    for line in raw.splitlines():
        m = re.match(rb'p:(\d+);d:(\d+);a:(.*)$', line)
        if not m:
            continue
        arr, _ = php_load(m.group(3))
        acts = [json.loads(a) for a in (arr.get(2) or {}).values()]
        turns.append({'player': int(m.group(1)), 'day': int(m.group(2)), 'actions': acts})
    return states, turns


def unit_name(a):
    u = a.get('newUnit') or a.get('unit') or {}
    g = u.get('global') if isinstance(u, dict) else None
    return g.get('units_name') if isinstance(g, dict) else None


if __name__ == '__main__':
    for path in sys.argv[1:]:
        states, turns = read_replay(path)
        g0, gl = states[0], states[-1]
        players = list(g0['players'].values())
        last = {p['id']: p for p in gl['players'].values()}
        print(f"== {g0['name']} · mapa {g0['maps_id']} · {len(states)} estados · último dia {gl['day']} · nevoeiro {g0['fog']}")
        for p in players:
            lp = last[p['id']]
            print(f"   jogador {p['id']} (ordem {p['order']}) CO {p['co_id']} {p['co_image']} · eliminado no fim: {lp['eliminated']}")
        kinds = Counter(a.get('action') for t in turns for a in t['actions'])
        print('   ações:', dict(kinds.most_common()))
        builds = defaultdict(list)
        for t in turns:
            for a in t['actions']:
                if a.get('action') == 'Build' and t['day'] <= 7:
                    builds[(t['player'], t['day'])].append(unit_name(a))
        for p in players:
            seq = [f"d{d}:" + '+'.join(builds[(p['id'], d)]) for d in range(1, 8) if builds[(p['id'], d)]]
            print(f"   compras de {p['id']} (dias 1-7):", ' '.join(seq))
