"""Checks the patched NEON_LUA bridge: (1) without the DLL it behaves like the original Lua,
(2) with a stand-in 'neon' table backed by the C++ model it produces the same grid_logic_var values."""
import random, re, subprocess, sys
from lupa import LuaRuntime
sys.path.insert(0, 'tests')
orig_path, patched_path, driver = sys.argv[1:4]
PRELUDE = open('tests/compare_with_lua.py').read().split("PRELUDE = r'''")[1].split("'''")[0]

def runtime(path):
    lua = LuaRuntime(unpack_returned_tuples=True); lua.execute(PRELUDE)
    lua.execute(open(path, encoding='latin-1').read()); return lua

orig, patched = runtime(orig_path), runtime(patched_path)
inc = open('src/NeonLegacyGroups.inc').read()
geo_names = ('LARGE_GEO_COUNT', 'SMALL_GEO_COUNT')
geo = set()
for n in geo_names:
    geo |= {int(h, 16) for h in re.findall(r'0x([0-9A-F]{8})', re.search(r'"%s".*\{(.*)\}' % n, inc).group(1))}
groups = sorted({int(h, 16) for h in re.findall(r'0x(BB35[0-9A-F]{4})', inc)} - geo - {0xBB350079})  # BB350079: NEON-only group, not in the Lua
rng = random.Random(7)

def setup(lua, counts, inputs):
    G = lua.globals()
    G.COUNTS = lua.table_from(counts); G.TRENDS = lua.table_from({1: inputs[0], 2: inputs[1], 3: inputs[2], 4: inputs[3], 5: inputs[4]})
    G.DIFF = inputs[7]; G.game.g_power_consumed = inputs[5]; G.game.g_power_production_capacity = inputs[6]
    return G

def snapshot(G):
    return {k: float(v) for k, v in G.grid_logic_var.items() if isinstance(v, (int, float))}

for mode in ('no-dll', 'dll'):
    bad = 0
    for c in range(40):
        counts = {g: rng.randint(1, 3) for g in rng.sample(groups, rng.randint(0, 30))}
        inputs = [rng.randint(0, 300000), rng.randint(0, 40000), rng.randint(0, 40000), rng.randint(0, 400000),
                  rng.randint(0, 100000), rng.randint(0, 300000), rng.randint(1, 400000), rng.randint(0, 2)]
        Go = setup(orig, counts, inputs); ro = {r: Go.run_grid_balance_variables(r) for r in 'TDXIBP'}; so = snapshot(Go)
        Gp = setup(patched, counts, inputs)
        if mode == 'dll':
            lines = []
            for g, n in counts.items():
                kva = Gp.kva_rating['ID_%08X' % g] or 0; mwh = Gp.mwh_rating['ID_%08X_A' % g] or Gp.mwh_rating['ID_%08X' % g] or 0
                lines += ['B %08X %r %r 0' % (g, float(kva), float(mwh))] * n
            state = {}
            def update(*args):
                state['inputs'] = list(args); return True
            def export(grid, company):
                text = '\n'.join(lines + ['I ' + ' '.join(str(x) for x in state['inputs'])])
                out = subprocess.run([driver], input=text, capture_output=True, text=True).stdout.split('\n')
                state['ret'] = {}
                for l in out:
                    p = l.split()
                    if len(p) == 3 and p[0] == 'G': grid[p[1]] = float(p[2])
                    if len(p) == 3 and p[0] == 'C': company[p[1]] = float(p[2])
                    if len(p) == 3 and p[0] == 'R': state['ret'][p[1]] = float(p[2])
            Gp.neon = patched.table_from({'update': update, 'export': export, 'grid': lambda r: state['ret'][r]})
        else:
            Gp.neon = patched.table_from({})
        rp = {r: Gp.run_grid_balance_variables(r) for r in 'TDXIBP'}; sp = snapshot(Gp)
        diffs = [k for k in so if abs(so[k] - sp.get(k, float('nan'))) > 1e-6 * max(1, abs(so[k]))]
        diffs += ['ret ' + r for r in 'TDXIBP' if abs(float(ro[r]) - float(rp[r])) > 1e-6 * max(1, abs(float(ro[r])))]
        if diffs: bad += 1; print(mode, 'city', c, diffs[:6])
    print(mode, ': 40 cities, failing', bad)
