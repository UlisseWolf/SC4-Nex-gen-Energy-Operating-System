"""Checks the DLL-only NEON_LUA.
(1) With a stand-in 'neon' table backed by the C++ model it gives the same grid_logic_var values and T/D/X/I/B/P as
    the original Lua (ratings fed to the model come from the full tables of the bridge version).
(2) Without the DLL it loads, run_grid_balance_variables() raises no error, returns 0 and keeps the rewards locked.
usage (from the project folder): python tests/dll_only_test.py <original NEON_LUA> lua/NEON_LUA.txt lua/NEON_LUA_DLL_ONLY.txt <model_driver>"""
import random, re, subprocess, sys
from lupa import LuaRuntime
orig_path, full_path, only_path, driver = sys.argv[1:5]
PRELUDE = open('tests/compare_with_lua.py').read().split("PRELUDE = r'''")[1].split("'''")[0]

def runtime(path):
    lua = LuaRuntime(unpack_returned_tuples=True); lua.execute(PRELUDE)
    lua.execute(open(path, encoding='latin-1').read()); return lua

orig, full, only = runtime(orig_path), runtime(full_path), runtime(only_path)
inc = open('src/NeonLegacyGroups.inc').read()
geo = set()
for n in ('LARGE_GEO_COUNT', 'SMALL_GEO_COUNT'):
    geo |= {int(h, 16) for h in re.findall(r'0x([0-9A-F]{8})', re.search(r'"%s".*\{(.*)\}' % n, inc).group(1))}
groups = sorted({int(h, 16) for h in re.findall(r'0x(BB35[0-9A-F]{4})', inc)} - geo - {0xBB350079})  # BB350079: NEON-only group, not in the Lua
rng = random.Random(11)
F = full.globals()

def setup(lua, counts, inputs):
    G = lua.globals()
    G.COUNTS = lua.table_from(counts); G.TRENDS = lua.table_from({1: inputs[0], 2: inputs[1], 3: inputs[2], 4: inputs[3], 5: inputs[4]})
    G.DIFF = inputs[7]; G.game.g_power_consumed = inputs[5]; G.game.g_power_production_capacity = inputs[6]
    return G

def snapshot(G):
    return {k: float(v) for k, v in G.grid_logic_var.items() if isinstance(v, (int, float))}

bad = 0
for c in range(100):
    counts = {g: rng.randint(1, 3) for g in rng.sample(groups, rng.randint(0, 30))}
    inputs = [rng.randint(0, 300000), rng.randint(0, 40000), rng.randint(0, 40000), rng.randint(0, 400000),
              rng.randint(0, 100000), rng.randint(0, 300000), rng.randint(1, 400000), rng.randint(0, 2)]
    Go = setup(orig, counts, inputs); ro = {r: Go.run_grid_balance_variables(r) for r in 'TDXIBP'}; so = snapshot(Go)
    Gp = setup(only, counts, inputs)
    lines = []
    for g, n in counts.items():
        kva = F.kva_rating['ID_%08X' % g] or 0; mwh = F.mwh_rating['ID_%08X_A' % g] or F.mwh_rating['ID_%08X' % g] or 0
        lines += ['B %08X %r %r 0' % (g, float(kva), float(mwh))] * n
    state = {}
    def update(*args):
        state['inputs'] = list(args); return True
    def export(grid, company, *tables):
        out = subprocess.run([driver], input='\n'.join(lines + ['I ' + ' '.join(str(x) for x in state['inputs'])]),
                             capture_output=True, text=True).stdout.split('\n')
        state['ret'] = {}
        for l in out:
            p = l.split()
            if len(p) == 3 and p[0] == 'G': grid[p[1]] = float(p[2])
            if len(p) == 3 and p[0] == 'C': company[p[1]] = float(p[2])
            if len(p) == 3 and p[0] == 'R': state['ret'][p[1]] = float(p[2])
    Gp.neon = only.table_from({'update': update, 'export': export, 'grid': lambda r: state['ret'].get(r)})
    rp = {r: Gp.run_grid_balance_variables(r) for r in 'TDXIBP'}; sp = snapshot(Gp)
    diffs = [k for k in so if abs(so[k] - sp.get(k, float('nan'))) > 1e-6 * max(1, abs(so[k]))]
    diffs += ['ret ' + r for r in 'TDXIBP' if abs(float(ro[r]) - float(rp[r])) > 1e-6 * max(1, abs(float(ro[r])))]
    # W2E live output shown by the W2E query
    for k in ('ID_BB3500D0', 'ID_BB3501D0'):
        if abs(float(Go.mwh_rating[k]) - float(Gp.mwh_rating[k])) > 1e-6: diffs.append('mwh_rating.' + k)
    if diffs: bad += 1; print('dll city', c, diffs[:6])
print('dll : 100 cities, failing', bad)

# without the DLL
nodll = runtime(only_path); G = nodll.globals(); G.neon = nodll.table_from({})
setup(nodll, {0xBB3500C0: 2}, [1000, 0, 0, 2000, 0, 900, 5000, 1])
rets = {r: G.run_grid_balance_variables(r) for r in 'TDXIBP'}
G.run_grid_balance_variables()
warn = nodll.eval('function() return (neon == nil or neon.update == nil) end')()
print('no-dll: returns', rets, '| warning trigger', warn)

# every reward condition and advice trigger runs without errors, with and without the DLL
for mode in ('dll', 'no-dll'):
    lua = LuaRuntime(unpack_returned_tuples=True); lua.execute(PRELUDE)
    lua.execute('ALL = {}; create_reward_cityplanning = function() local a = {} table.insert(ALL, a) return a end;'
                'create_advice_utilities = create_reward_cityplanning; create_advice_utilities_with_base = create_reward_cityplanning; '
                'reward_state = {AVAILABLE = "AVAILABLE"}')
    lua.execute(open(only_path, encoding='latin-1').read())
    G = setup(lua, {0xBB3500C0: 2, 0xBB350120: 1, 0xBB350030: 3}, [50000, 0, 0, 60000, 0, 40000, 80000, 1])
    if mode == 'dll':
        lines = ['B BB3500C0 18750.0 7500.0 0'] * 2 + ['B BB350120 10000.0 0.0 0', 'B BB350030 500.0 0.0 0'] * 1
        st = {}
        def upd(*a): st['i'] = list(a); return True
        def exp(grid, company, *tables):
            out = subprocess.run([driver], input='\n'.join(lines + ['I ' + ' '.join(str(x) for x in st['i'])]), capture_output=True, text=True).stdout
            st['r'] = {}
            for l in out.split('\n'):
                p = l.split()
                if len(p) == 3 and p[0] == 'G': grid[p[1]] = float(p[2])
                if len(p) == 3 and p[0] == 'C': company[p[1]] = float(p[2])
                if len(p) == 3 and p[0] == 'R': st['r'][p[1]] = float(p[2])
        G.neon = lua.table_from({'update': upd, 'export': exp, 'grid': lambda r: st['r'].get(r)})
    else:
        G.neon = lua.table_from({})
    check = lua.eval('''function()
        local n, errs, unlocked = 0, {}, 0
        for _, a in ipairs(ALL) do
            if a.condition then
                n = n + 1
                local ok, v = pcall(a.condition)
                if not ok then table.insert(errs, tostring(v)) elseif v == reward_state.AVAILABLE then unlocked = unlocked + 1 end
            end
            if type(a.trigger) == "string" then
                local f = (loadstring or load)("return " .. a.trigger)
                local ok, v = pcall(f)
                if not ok then table.insert(errs, "trigger " .. a.trigger .. ": " .. tostring(v)) end
            end
        end
        return n, #errs, errs[1], unlocked
    end''')
    n, nerr, first, unlocked = check()
    print(mode, ': %d reward conditions, %d errors%s, %d available' % (n, nerr, (' (' + str(first) + ')') if first else '', unlocked))
