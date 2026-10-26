"""Runs the ORIGINAL NEON Lua run_grid_balance_variables() and the C++ model on the same random cities
and compares every grid_logic_var / power_company_buildings value and the six return values.
usage: python3 compare_with_lua.py NEON_LUA.txt model_driver [cities] [--exclude-geo]"""
import random, re, subprocess, sys
from lupa import LuaRuntime

lua_path, driver = sys.argv[1], sys.argv[2]
cities = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3].isdigit() else 200
exclude_geo = '--exclude-geo' in sys.argv
src = open(lua_path, encoding='latin-1').read()
inc = open('src/NeonLegacyGroups.inc').read()
groups = sorted({int(h, 16) for h in re.findall(r'0x(BB35[0-9A-F]{4})', inc)} - {0xBB350079})  # BB350079: NEON-only group, not in the Lua
geo = set()
for name in ('LARGE_GEO_COUNT', 'SMALL_GEO_COUNT'):
    m = re.search(r'"%s".*\{(.*)\}' % name, inc); geo |= {int(h, 16) for h in re.findall(r'0x([0-9A-F]{8})', m.group(1))}

PRELUDE = r'''
hex2dec = function(h) return tonumber(h, 16) end
dbpf = { get_exemplar_property_value = function(g, i, p) return 1000 end }
COUNTS = {}; TRENDS = {}; DIFF = 0
sc4game = { automata = { get_source_building_count = function(og) return COUNTS[og] or 0 end } }
game_trends = { G_POWER_DEMANDED = 1, G_POWER_EXPORTED = 2, G_POWER_IMPORTED = 3, G_POWER_PRODUCED = 4, G_GARBAGE_TO_ENERGY = 5 }
game_difficulty_level = { EASY = 0, MEDIUM = 1, HARD = 2 }
game = setmetatable({ trend_value = function(t, i) return TRENDS[t] or 0 end,
                      difficulty_level = function() return DIFF end, g_bridge_tile_count = 0 },
                    { __index = function() return 0 end })
local any = { __index = function() return 0 end }
tuning_constants = setmetatable({}, any); advice_moods = setmetatable({}, any); reward_state = setmetatable({}, any)
create_advice_utilities = function() return {} end
create_reward_cityplanning = function() return {} end
create_advice_utilities_with_base = function() return {} end
dofile = function() end
'''
lua = LuaRuntime(unpack_returned_tuples=True)
lua.execute(PRELUDE)
lua.execute(src)
G = lua.globals()

def lua_value(table, key):
    v = table['ID_%08X' % key]
    return float(v) if v is not None else None

worst = 0.0; failures = 0; MISSING = set()
rng = random.Random(1234)
for c in range(cities):
    pool = [g for g in groups if not (exclude_geo and g in geo)]
    picked = rng.sample(pool, rng.randint(0, 40))
    counts = {g: rng.randint(1, 4) for g in picked}
    inputs = [rng.randint(0, 400000), rng.randint(0, 50000), rng.randint(0, 50000), rng.randint(0, 500000),
              rng.randint(0, 200000), rng.randint(0, 400000), rng.randint(1, 500000), rng.randint(0, 2)]
    # --- Lua side
    G.COUNTS = lua.table_from({g: n for g, n in counts.items()})
    G.TRENDS = lua.table_from({1: inputs[0], 2: inputs[1], 3: inputs[2], 4: inputs[3], 5: inputs[4]})
    G.DIFF = inputs[7]
    G.game.g_power_consumed = inputs[5]; G.game.g_power_production_capacity = inputs[6]
    rets = {r: G.run_grid_balance_variables(r) for r in 'TDXIBP'}
    lv = {}
    for k, v in G.grid_logic_var.items():
        if isinstance(v, (int, float)): lv[k] = float(v)
    for k, v in G.power_company_buildings.items(): lv[k] = float(v)
    # --- C++ side (same per-building kVA/MWh the Lua tables use)
    lines = []
    for g, n in counts.items():
        kva = lua_value(G.kva_rating, g) or 0.0
        mwh = lua_value(G.mwh_rating, g)
        a = G.mwh_rating['ID_%08X_A' % g]
        if a is not None: mwh = float(a)
        for _ in range(n): lines.append('B %08X %r %r 0' % (g, kva, mwh or 0.0))
    lines.append('I ' + ' '.join(str(x) for x in inputs))
    out = subprocess.run([driver], input='\n'.join(lines), capture_output=True, text=True).stdout.split('\n')
    cv = {}; cr = {}
    for l in out:
        p = l.split()
        if len(p) == 3 and p[0] in 'GC': cv[p[1]] = float(p[2])
        if len(p) == 3 and p[0] == 'R': cr[p[1]] = float(p[2])
    bad = []
    for k, v in lv.items():
        if k in ('RANDVOLTAGE', 'VOLTVALUE', 'DIST_SUB_COST_MONTHLY_A', 'DIST_SUB_COST_MONTHLY_B'): continue
        if k not in cv:
            MISSING.add(k); continue
        tol = 1e-6 * max(1.0, abs(v))
        if abs(cv[k] - v) > tol: bad.append((k, v, cv[k]))
        else: worst = max(worst, abs(cv[k] - v))
    for r in 'TDXIBP':
        if abs(cr[r] - float(rets[r])) > 1e-6 * max(1, abs(float(rets[r]))): bad.append(('ret ' + r, rets[r], cr[r]))
    if bad:
        failures += 1
        if failures <= 3: print('city', c, 'mismatches:', bad[:8])
print('cities: %d, failing: %d, compared values per city: ~%d' % (cities, failures, len(lv)))
print('names only in the initial Lua table:', sorted(MISSING))
