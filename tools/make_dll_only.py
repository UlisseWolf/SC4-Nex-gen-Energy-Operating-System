"""Builds the "DLL only" NEON_LUA from the bridge version (lua/NEON_LUA.txt).

usage: python tools/make_dll_only.py lua/NEON_LUA.txt <mod LTEXT dump .json> lua/NEON_LUA_DLL_ONLY.txt

Removed (the DLL computes them):
  * the Lua version of run_grid_balance_variables (run_grid_balance_variables_lua);
  * every kva_rating / mwh_rating entry that no reward, no LTEXT and no W2E update reads.
Kept: reward system, hex id tables, unlock_variables, grid_logic_var, power_company_buildings, costs, storage stacks,
voltage_variance and the cost functions used by the LTEXTs, and the bridge (without its Lua fallback)."""
import json, re, sys

src, ltext_json, dst = sys.argv[1:4]
text = open(src, 'rb').read().decode('latin-1')
nl = '\r\n' if '\r\n' in text else '\n'
lines = text.split(nl)

def find(pattern, start=0):
    for n in range(start, len(lines)):
        if re.match(pattern, lines[n]):
            return n
    raise SystemExit('not found: ' + pattern)

# ------------------------------------------------------------------ keys still read somewhere
reward_start = find(r'-- NEON REWARD SYSTEM --')
users = nl.join(lines[reward_start:])
for _, s in json.load(open(ltext_json)).values():
    users += '\n' + '\n'.join(re.findall(r'#([^#\r\n]{1,300})#', s))
needed = {t: set(re.findall(t + r'\.(ID_[0-9A-Fa-f]{8}(?:_A)?)', users)) for t in ('kva_rating', 'mwh_rating')}
# the bridge's W2E update reads and writes these
for m in re.finditer(r'mwh_rating\.(ID_BB35[0-9A-F]{4}(?:_A)?)', nl.join(lines[find(r'function neon_update_waste_to_energy_ratings'):reward_start])):
    needed['mwh_rating'].add(m.group(1))

def prune(table):
    start = find(table + r' *= *\{')
    end = find(r'\}', start)
    kept, dropped = [], 0
    for l in lines[start + 1:end]:
        m = re.match(r'\s*(ID_[0-9A-Fa-f]{8}(?:_A)?)\s*=', l)
        if m and m.group(1) in needed[table]:
            kept.append(l)
        elif m:
            dropped += 1
    # commas: every entry but the last one ends with ','
    out = []
    for i, l in enumerate(kept):
        m = re.match(r'(\s*ID_\w+\s*=\s*.*?)(\s*,?)(\s*--.*)?$', l)
        body, comment = m.group(1).rstrip(), m.group(3) or ''
        out.append(body + (',' if i < len(kept) - 1 else '') + comment)
    lines[start + 1:end] = out
    return len(kept), dropped

report = {t: prune(t) for t in ('kva_rating', 'mwh_rating')}

# ------------------------------------------------------------------ remove the Lua grid calculation
a = find(r'-- NEON CONTROLLER--')
b = find(r'function voltage_variance')
removed_fn = b - a
lines[a:b] = ['-- NEON CONTROLLER --',
              '-- run_grid_balance_variables() is computed by SC4NEON.dll (see the NEON DLL BRIDGE below).']

# kva_rating of the Maxis gas plant read the MWh property (0x09A44AC9) instead of the kVA one (0xE652E51F)
k0 = find(r'kva_rating *= *\{')
k1 = find(r'\}', k0)
for n in range(k0, k1):
    if 'ID_BB3501A4' in lines[n]:
        lines[n] = lines[n].replace('hex2dec("09A44AC9")', 'hex2dec("E652E51F")')

# ------------------------------------------------------------------ bridge without the Lua fallback
text = nl.join(lines)
old_alias = 'run_grid_balance_variables_lua = run_grid_balance_variables' + nl
assert old_alias in text
text = text.replace(old_alias, '')
old_guard = ('    if (neon.update == nil) then' + nl + '        return run_grid_balance_variables_lua(ret_type)' + nl + '    end' + nl)
assert old_guard in text
text = text.replace(old_guard, (
    '    if (neon.update == nil) then' + nl +
    '        -- SC4NEON.dll is not installed: the grid values stay at 0 and the rewards stay locked.' + nl +
    '        if (ret_type ~= nil) then return 0 end' + nl +
    '        return' + nl +
    '    end' + nl))
old_ret = '        return neon.grid(ret_type)' + nl
assert old_ret in text
text = text.replace(old_ret, '        return neon.grid(ret_type) or 0' + nl)
text = text.replace(
    '-- When SC4NEON.dll is installed, run_grid_balance_variables() is computed in C++ by the DLL.' + nl +
    '-- Without the DLL, the original Lua version below (run_grid_balance_variables_lua) is used as before.' + nl,
    '-- run_grid_balance_variables() is computed in C++ by SC4NEON.dll, which is REQUIRED by this version.' + nl +
    '-- Without the DLL the grid values stay at 0, the rewards stay locked and the advisor warns the player.' + nl)
text = text.replace('-- NEON DLL bridge added 2026 (works with or without SC4NEON.dll) --',
                    '-- DLL only version 2026: requires SC4NEON.dll --')

# the DLL also writes the kVA / MWh of the lots in the city into kva_rating / mwh_rating (query texts)
old_exp = '        neon.export(grid_logic_var, power_company_buildings)' + nl
assert old_exp in text
text = text.replace(old_exp, '        neon.export(grid_logic_var, power_company_buildings, kva_rating, mwh_rating)' + nl)

# rating entries that are not in the trimmed tables (lots the DLL fills in at run time) read as 0, never nil
guard = ('-- Missing kva_rating / mwh_rating entries read as 0 (SC4NEON.dll fills in the lots that are in the city).' + nl +
         'setmetatable(kva_rating, {__index = function() return 0 end})' + nl +
         'setmetatable(mwh_rating, {__index = function() return 0 end})' + nl)
anchor = 'if (neon == nil) then neon = {} end' + nl
assert anchor in text
text = text.replace(anchor, anchor + guard, 1)

# advisor message when the DLL is missing (inserted before the reward system)
warn = nl.join([
    '-- warning shown when SC4NEON.dll is missing',
    "a = create_advice_utilities('bb354101')",
    '',
    'a.trigger  = "neon == nil or neon.update == nil"',
    'a.once = 1',
    'a.timeout = tuning_constants.ADVICE_TIMEOUT_LONG',
    'a.title   = [[text@bb354201]]',
    'a.message   = [[text@bb354301]]',
    'a.priority  = tuning_constants.ADVICE_PRIORITY_URGENT',
    'a.persist = 1',
    ''])
warn += nl.join([
    '-- required dependencies (transformers, distribution substations, transmission stations) not installed',
    "a = create_advice_utilities('bb354103')",
    '',
    'a.trigger  = "grid_logic_var.NEON_MISSING_DEPENDENCIES ~= nil and grid_logic_var.NEON_MISSING_DEPENDENCIES > 0"',
    'a.once = 1',
    'a.timeout = tuning_constants.ADVICE_TIMEOUT_LONG',
    'a.title   = [[text@bb354203]]',
    'a.message   = [[text@bb354303]]',
    'a.priority  = tuning_constants.ADVICE_PRIORITY_URGENT',
    'a.persist = 1',
    ''])
warn += nl.join([
    '-- power cut by the NEON grid limits (SC4NEON.ini [Enforcement])',
    "a = create_advice_utilities('bb354102')",
    '',
    'a.trigger  = "grid_logic_var.NEON_BLACKOUT_POWER ~= nil and grid_logic_var.NEON_BLACKOUT_POWER > 0"',
    'a.once = 1',
    'a.timeout = tuning_constants.ADVICE_TIMEOUT_LONG',
    'a.title   = [[text@bb354202]]',
    'a.message   = [[text@bb354302]]',
    'a.priority  = tuning_constants.ADVICE_PRIORITY_URGENT',
    'a.persist = 1',
    ''])
marker = "-- introducing base, peak, and intermediate loads"
assert marker in text
text = text.replace(marker, warn + marker, 1)

open(dst, 'wb').write(text.encode('latin-1'))
print('kva_rating kept/dropped %d/%d, mwh_rating kept/dropped %d/%d, grid function lines removed %d, lines %d -> %d'
      % (*report['kva_rating'], *report['mwh_rating'], removed_fn, len(open(src, 'rb').read().split(b'\n')),
         len(text.split(nl))))
