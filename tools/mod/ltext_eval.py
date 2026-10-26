"""Evaluates every #...# Lua token of every NEON LTEXT against the patched NEON_LUA (DLL mode, C++ model behind
neon.*) and reports the tokens that fail or give nil. Property/money tokens (d:, m:) and plain words are skipped."""
import json, os, re, subprocess, sys, random
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
from lupa import LuaRuntime
lua_file, driver = sys.argv[1], sys.argv[2]
PRELUDE = open(os.path.join(ROOT, 'tests', 'compare_with_lua.py')).read().split("PRELUDE = r'''")[1].split("'''")[0]
lua = LuaRuntime(unpack_returned_tuples=True); lua.execute(PRELUDE)
lua.execute(open(lua_file, encoding='latin-1').read())
G = lua.globals()
inc = open(os.path.join(ROOT, 'src', 'NeonLegacyGroups.inc')).read()
groups = sorted({int(h, 16) for h in re.findall(r'0x(BB35[0-9A-F]{4})', inc)})
rng = random.Random(3)
counts = {g: rng.randint(1, 3) for g in rng.sample(groups, 60)}
inputs = [120000, 8000, 5000, 150000, 20000, 110000, 160000, 1]
G.COUNTS = lua.table_from(counts); G.TRENDS = lua.table_from({1: inputs[0], 2: inputs[1], 3: inputs[2], 4: inputs[3], 5: inputs[4]})
G.DIFF = inputs[7]; G.game.g_power_consumed = inputs[5]; G.game.g_power_production_capacity = inputs[6]
lines = []
for g, n in counts.items():
    kva = G.kva_rating['ID_%08X' % g] or 0; mwh = G.mwh_rating['ID_%08X_A' % g] or G.mwh_rating['ID_%08X' % g] or 0
    lines += ['B %08X %r %r 0' % (g, float(kva), float(mwh))] * n
state = {}
def update(*a): state['in'] = list(a); return True
def export(grid, company, *tables):
    out = subprocess.run([driver], input='\n'.join(lines + ['I ' + ' '.join(str(x) for x in state['in'])]), capture_output=True, text=True).stdout
    state['ret'] = {}
    for l in out.split('\n'):
        p = l.split()
        if len(p) == 3 and p[0] == 'G': grid[p[1]] = float(p[2])
        if len(p) == 3 and p[0] == 'C': company[p[1]] = float(p[2])
        if len(p) == 3 and p[0] == 'R': state['ret'][p[1]] = float(p[2])
G.neon = lua.table_from({'update': update, 'export': export, 'grid': lambda r: state['ret'].get(r)})
G.run_grid_balance_variables()
lt = json.load(open('ltext/all.json'))
evaluate = lua.eval('function(src) local f, e = loadstring and loadstring("return " .. src) or load("return " .. src); if not f then return "COMPILE", e end; local ok, v = pcall(f); if not ok then return "ERROR", v end; return "OK", v end')
skip = re.compile(r'^(?:[dm]:[0-9A-Fa-f]{8}|link_id|city|City|mayor|advisor|POWER_COMPANY_NAME)$')
report = {}
for key, (f, s) in sorted(lt.items()):
    for tok in re.findall(r'#([^#\r\n]{1,300})#', s):
        if skip.match(tok.strip()): continue
        status, val = evaluate(tok)
        if status != 'OK' or val is None:
            report.setdefault(tok, (status, str(val)[:90], set()))[2].add(f + ':' + key)
for tok, (st, v, where) in sorted(report.items(), key=lambda x: x[1][0]):
    print('%-6s %-70.70s %s  [%d LTEXT: %s]' % (st, tok, v, len(where), ', '.join(sorted(where))[:120]))
print('tokens failing:', len(report))
