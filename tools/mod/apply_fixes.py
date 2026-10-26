"""Applies the NEON compatibility fixes to a copy of the Colossus Addon Mod (NEON V 0.1.1).

usage: python apply_fixes.py <mod folder> <output folder> <NEON_LUA.txt with the DLL bridge>
Writes every change to <output folder>/NEON_fixes_log.md."""
import math, os, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dbpfedit import Package, Exemplar, ltext_decode, ltext_encode

SRC, DST, LUA = sys.argv[1:4]
LTEXT, UI, COHORT, LUA_T = 0x2026960B, 0x00000000, 0x05342861, 0xCA63E2A3
UI_GROUP, TXT_GROUP = 0x96A006B0, 0xBB352500
P_OG, P_UI, P_TARGETS, P_KVA, P_MWH, P_NAME = 0xAA1DD396, 0x2A499F85, 0x0062E78A, 0xE652E51F, 0x09A44AC9, 0x20
OG_COAL, OG_OIL, OG_GAS, OG_FISSION, OG_FUSION, OG_GEO = 0x1946409F, 0xD6B169D9, 0x5512235E, 0xA945A10D, 0xB680D7E0, 0x1F221780
OG_SOLAR, OG_W2E, OG_WIND, OG_GEN, OG_STORAGE = 0x7134683C, 0xEC9175AA, 0xC78E0054, 0xB075C142, 0x861A7248
OG_I, OG_B, OG_P = 0x0BADB9AC, 0x18E64EA5, 0x7283DCD7
CLASS_NAME = {OG_I: 'Intermediate', OG_B: 'Base Load', OG_P: 'Peak'}

# legacy group -> (NEON groups to add, load class); classes follow NEON_LUA and the Reader templates
PLANTS = {
    0xBB3501C0: ([OG_COAL], OG_B), 0xBB3500B8: ([OG_COAL], OG_B), 0xBB3500BA: ([OG_COAL], OG_B), 0xBB3500C0: ([OG_COAL], OG_B),
    0xBB3501A4: ([OG_GAS], OG_P), 0xBB3500A0: ([OG_GAS], OG_P),
    0xBB350002: ([OG_GEN, OG_OIL], OG_P), 0xBB350003: ([OG_GEN, OG_OIL], OG_P), 0xBB350100: ([OG_GEN, OG_GAS], OG_P),
    0xBB350010: ([OG_GEN, OG_SOLAR], OG_I),
    0xBB350171: ([OG_GEO], OG_B), 0xBB350070: ([OG_GEO], OG_B), 0xBB350071: ([OG_GEO], OG_B),
    0xBB350088: ([OG_FUSION], OG_B), 0xBB350078: ([OG_FISSION], OG_B), 0xBB350080: ([OG_FISSION], OG_B),
    0xBB350090: ([OG_OIL], OG_P), 0xBB350150: ([OG_SOLAR], OG_I), 0xBB350151: ([OG_SOLAR], OG_I),
    0xBB3500D0: ([OG_W2E], OG_B), 0xBB350160: ([OG_WIND], OG_I),
}
# MWh from the NEON_LUA mwh_rating table, for the patches that carried the copied 5200 MWh / 13000 kVA
LUA_MWH = {0xBB3501C0: 1250, 0xBB3500B8: 8800, 0xBB3500BA: 21000, 0xBB3500A0: 15000, 0xBB350002: 100, 0xBB350003: 400,
           0xBB350100: 75, 0xBB350010: 5, 0xBB350171: 2200, 0xBB350070: 4600, 0xBB350071: 6000, 0xBB350150: 73}
# Power produced (0x27812852) of the target lots, as reported by SC4NEON.log in game (24-25 Oct 2026).
# NEON rule: MWh Rating = power produced, kVA = 2.5 x MWh.
GAME_MWH = {0x70F4A14F: 6000, 0x6DD69839: 29500, 0x490FF4A1: 100, 0x65FC4DF7: 1500, 0x3A556B6C: 25000, 0x690A0D1A: 2500}
UI_REPOINT = {  # patch instance -> (new query UI, reason)
    0x007C196E: (0xBB353150, 'SM2 GE Solar used the Maxis solar query (BB353151); BB353150 was made for it and unused'),
    0x91097707: (0xBB353020, 'query UI BB35314E does not exist; transformer query used'),
    0xFEC2067D: (0xBB353020, 'query UI BB35314F does not exist; transformer query used'),
    0x6FBB638B: (0xBB353200, 'query UI BB353140 does not exist; power company query used'),
}
log = []


def note(file, what):
    log.append((file, what))


def walk(folder):
    for dp, _, fn in os.walk(folder):
        for f in sorted(fn):
            if f.lower().endswith('.dat'):
                yield os.path.join(dp, f)


# ------------------------------------------------------------------ copy and load
if os.path.exists(DST):
    shutil.rmtree(DST)
shutil.copytree(SRC, DST)
pk = {os.path.basename(p): Package(p) for p in walk(DST)}
path_of = {os.path.basename(p): p for p in walk(DST)}

def ltext_index():
    idx = {}
    for name, p in pk.items():
        for e in p.entries:
            if e.t == LTEXT:
                idx[(e.g, e.i)] = (name, e)
    return idx

# ------------------------------------------------------------------ A. Lua with the DLL bridge
core = pk['NEON_Core_Files.dat']
e = core.find(LUA_T)[0]
e.data = open(LUA, 'rb').read()
DLL_ONLY = b'DLL only version' in e.data
if DLL_ONLY:
    note('NEON_Core_Files.dat', 'NEON_LUA replaced with the DLL-only version (made by tools/make_dll_only.py): the Lua grid '
         'calculation and the unused kva_rating / mwh_rating entries are removed; SC4NEON.dll is required')
    note('NEON_Core_Files.dat', 'kva_rating.ID_BB3501A4 (Maxis gas plant) now reads the kVA property 0xE652E51F instead of MWh 0x09A44AC9')
    loc = pk['NEON_Locale_Files_en.dat']
    for inst, t in ((0xBB354201, 'NEON needs SC4NEON.dll'),
                    (0xBB354301, 'SC4NEON.dll is not installed. This version of NEON computes the power grid in the DLL: '
                                 'without it the grid values stay at 0 and the NEON rewards stay locked.\r\n\r\n'
                                 'Put SC4NEON.dll in the Plugins folder and restart the game.')):
        loc.add(LTEXT, 0x6A231EA4, inst, ltext_encode(t))
        note('NEON_Locale_Files_en.dat', 'new LTEXT 6A231EA4/%08X for the "SC4NEON.dll missing" advisor message' % inst)
    for inst, t in ((0xBB354202, 'Power cut: the grid cannot deliver'),
                    (0xBB354302, 'NEON is cutting #math.floor(grid_logic_var.NEON_BLACKOUT_POWER)# MWh of power: your grid can only '
                                 'deliver #math.floor(grid_logic_var.NEON_DELIVERABLE_POWER)# MWh of what the city needs, so some '
                                 'blocks are left without power.\r\n\r\n'
                                 'Load balance: Base, Intermediate and Peak plants can serve '
                                 '#math.floor(grid_logic_var.NEON_LOADBALANCE_POWER)# MWh. Base plants cannot follow the demand: '
                                 'build Peak plants if the Peak shortfall is high.\r\n'
                                 'Infrastructure: transmission stations, distribution substations and transformers can carry '
                                 '#math.floor(grid_logic_var.NEON_INFRASTRUCTURE_POWER)# MWh.\r\n\r\n'
                                 'The Power Company office shows the details.')):
        loc.add(LTEXT, 0x6A231EA4, inst, ltext_encode(t))
        note('NEON_Locale_Files_en.dat', 'new LTEXT 6A231EA4/%08X for the "power cut" advisor message (grid limits enforced by SC4NEON.dll)' % inst)
    for inst, t in ((0xBB354203, 'NEON: substation lots are missing'),
                    (0xBB354303, 'NEON needs its substation dependencies, and some are not installed: transformers, distribution '
                                 'substations or transmission stations (#grid_logic_var.NEON_MISSING_DEPENDENCIES# of 3 kinds missing). '
                                 'Without them the power of your plants cannot reach the buildings.\r\n\r\n'
                                 'Install the substation packs listed in the NEON readme (SM2, PEG, DK1 and Homefryes substations) '
                                 'and restart the game. SC4NEON.log lists what was found.')):
        loc.add(LTEXT, 0x6A231EA4, inst, ltext_encode(t))
        note('NEON_Locale_Files_en.dat', 'new LTEXT 6A231EA4/%08X for the "missing substation dependencies" advisor message' % inst)
else:
    note('NEON_Core_Files.dat', 'NEON_LUA replaced with the version that has the DLL bridge (falls back to the Lua code without SC4NEON.dll)')

# ------------------------------------------------------------------ B. duplicated entries
for name, p in pk.items():
    for key in p.duplicates():
        copies = p.find(*key)
        keep = next((c for c in copies if '\r\n' in ltext_decode(c.data)[0]), copies[0]) if key[0] == LTEXT else copies[-1]
        for c in copies:
            if c is not keep:
                p.remove(c)
        note(name, 'removed duplicate entry %08X %08X %08X (kept one copy)' % key)

# ------------------------------------------------------------------ C1/C2. LTEXT format and division guard
guard = re.compile(r'/\s*grid_logic_var\.(SUP_GEN_[IBP]_POWER)\)')
for name, p in pk.items():
    for e in p.entries:
        if e.t != LTEXT:
            continue
        text, utf16 = ltext_decode(e.data)
        new = guard.sub(r'/ math.max(grid_logic_var.\1,1))', text)
        if not utf16 or new != text:
            e.data = ltext_encode(new)
            what = []
            if not utf16: what.append('stored without the UTF-16 LTEXT header, re-encoded')
            if new != text: what.append('division by SUP_GEN_x_POWER guarded with math.max(...,1)')
            note(name, 'LTEXT %08X %08X: %s' % (e.g, e.i, '; '.join(what)))

# ------------------------------------------------------------------ D/C3. plant query UIs: one "Actual Capacity" text per plant
def ui_entries():
    for name, p in pk.items():
        for e in p.entries:
            if e.t == UI and e.g == UI_GROUP:
                yield name, p, e

texts = ltext_index()
plant_ui_fix = {  # UI instance -> forced "Power Used" text instance
    0xBB3531D0: 0xBB3500D0,   # Maxis W2E is the large W2E group BB3500D0, the query showed small W2E (BB3501D0)
    0xBB353150: 0xBB350150,   # SM2 GE Solar query showed the Maxis solar plant
}
new_texts = {}  # (name of dat, instance) -> text
for name, p, e in list(ui_entries()):
    s = e.data.decode('latin-1')
    refs = [int(i, 16) for i in re.findall(r'captionres=\{bb352500,(bb35[0-9a-f]{4})\}', s)]
    if not refs:
        continue
    used = [r for r in refs if (r & 0xFFFFF000) == 0xBB350000 and (r & 0x800) == 0]
    actual = [r for r in refs if r not in used]
    if len(used) != 1 or len(actual) != 1:
        continue
    used_id, actual_id = used[0], actual[0]
    target_used = plant_ui_fix.get(e.i, used_id)
    target_actual = target_used | 0x800
    if (TXT_GROUP, target_used) not in texts and (name, target_used) not in new_texts:
        src = texts[(TXT_GROUP, used_id)][1]
        t = ltext_decode(src.data)[0].replace('ID_%08X' % used_id, 'ID_%08X' % target_used)
        new_texts[(name, target_used)] = t
    used_text = new_texts.get((name, target_used)) or ltext_decode(texts[(TXT_GROUP, target_used)][1].data)[0]
    cls = re.search(r'([IBP])_PERCENT', used_text).group(1)
    new_texts[(name, target_actual)] = ('#math.floor(mwh_rating.ID_%08X * (1 + (grid_logic_var.DEV_%s_POWER / '
                                        'math.max(grid_logic_var.SUP_GEN_%s_POWER,1))))#' % (target_used, cls, cls))
    s2 = s.replace('captionres={bb352500,%08x}' % used_id, 'captionres={bb352500,%08x}' % target_used)
    s2 = s2.replace('captionres={bb352500,%08x}' % actual_id, 'captionres={bb352500,%08x}' % target_actual)
    if s2 != s:
        e.data = s2.encode('latin-1')
        what = 'Actual Capacity text %08X (missing) -> %08X' % (actual_id, target_actual)
        if target_used != used_id:
            what += '; Power Used text %08X -> %08X' % (used_id, target_used)
        note(name, 'query UI %08X: %s' % (e.i, what))

# PV panels: new query UI BB353010, a copy of the SM2 GE solar query (Intermediate) showing the panel values
solar = next(e for n, p, e in ui_entries() if e.i == 0xBB353150)
s = solar.data.decode('latin-1')
s = s.replace('captionres={bb352500,bb350150}', 'captionres={bb352500,bb350010}')
s = s.replace('captionres={bb352500,bb350950}', 'captionres={bb352500,bb350810}')
pk['NEON_UI_Generator_Files.dat'].add(UI, UI_GROUP, 0xBB353010, s.encode('latin-1'))
note('NEON_UI_Generator_Files.dat', 'new query UI BB353010 for the SM2 Modular Solar Panels (copy of the solar query)')
new_texts[('NEON_UI_Generator_Files.dat', 0xBB350010)] = ('#math.floor(mwh_rating.ID_BB350010 * grid_logic_var.I_PERCENT * (1 + '
    '(grid_logic_var.DEV_I_POWER / math.max(grid_logic_var.SUP_GEN_I_POWER,1))))#')
new_texts[('NEON_UI_Generator_Files.dat', 0xBB350810)] = ('#math.floor(mwh_rating.ID_BB350010 * (1 + (grid_logic_var.DEV_I_POWER / '
    'math.max(grid_logic_var.SUP_GEN_I_POWER,1))))#')

# company names the UIs reference but nobody defined
for inst, cid in ((0x20000100, '00'), (0x20000117, '17'), (0x2000010E, '0E'), (0x20000119, '19')):
    new_texts[('NEON_Essential.dat', inst)] = '#company_name.ID_%s#' % cid

texts = ltext_index()
for (name, inst), t in sorted(new_texts.items()):
    if (TXT_GROUP, inst) in texts:
        continue
    pk[name].add(LTEXT, TXT_GROUP, inst, ltext_encode(t))
    texts[(TXT_GROUP, inst)] = (name, None)
    note(name, 'new LTEXT %08X %08X: %s' % (TXT_GROUP, inst, t))

# ------------------------------------------------------------------ D2. power company office: right-hand plant counts
# In the "Independent Power Plants" column three values were wired to the wrong row (the label instances are shifted
# by one against the value instances): Fission showed the Tidal count, Biomass the Microwave count, Microwave the Fission count.
OFFICE_FIX = {(172, 0x20000047): 0x20000046, (190, 0x2000004C): 0x2000004B, (317, 0x20000046): 0x2000004C}
office_pkg = pk['NEON_UI_Office.dat']
for e in office_pkg.entries:
    if e.t == UI and e.g == UI_GROUP and e.i == 0xBB353200:
        text = e.data.decode('latin-1')
        def fix_line(m):
            line = m.group(0)
            a = re.search(r'area=\((\d+),(\d+),', line)
            c = re.search(r'captionres=\{([0-9a-fA-F]+),([0-9a-fA-F]+)\}', line)
            if not a or not c or int(a.group(1)) < 800:
                return line
            key = (int(a.group(2)), int(c.group(2), 16))
            if key not in OFFICE_FIX:
                return line
            new_i = OFFICE_FIX[key]
            note('NEON_UI_Office.dat', 'office UI BB353200, right column row y=%d: value text %08X -> %08X' % (key[0], key[1], new_i))
            return line[:c.start(2)] + '%08x' % new_i + line[c.end(2):]
        text2 = re.sub(r'[^\r\n]+', fix_line, text)
        assert text2 != text
        e.data = text2.encode('latin-1')

# ------------------------------------------------------------------ E. exemplar patches
for name, p in pk.items():
    for e in p.entries:
        if e.t != COHORT:
            continue
        x = Exemplar(e.data)
        if not x.values(P_TARGETS):
            continue
        title = (x.values(P_NAME) or [''])[0]
        changes = []
        groups = list(x.values(P_OG, []))
        legacy = [g for g in groups if g >> 16 == 0xBB35]
        if e.i == 0xFEC2067D and x.values(P_TARGETS) == [0x7CC07882, 0xA90B4E29]:
            x.set(P_TARGETS, 0x03, [0x7CC07882, 0xB90B4DC3], True)
            changes.append('target A90B4E29 (the step-up transformer) -> B90B4DC3 (the inverter, as in NEON_LUA)')
        if e.i == 0xBE924296 and not legacy:
            groups += [0xBB350040]
            legacy = [0xBB350040]
            changes.append('added group BB350040: the X Small Powerpack had no NEON group and was never counted')
        if legacy and legacy[0] in (0xBB350040, 0xBB350041, 0xBB350042, 0xBB350043) and OG_STORAGE not in groups:
            groups.append(OG_STORAGE)
            changes.append('added NEON Power Storage group')
        if legacy and legacy[0] in PLANTS:
            add, cls = PLANTS[legacy[0]]
            missing = [g for g in add if g not in groups]
            if missing:
                groups += missing
                changes.append('added NEON fuel group(s) %s' % ', '.join('%08X' % g for g in missing))
            if not any(c in groups for c in CLASS_NAME):
                groups.append(cls)
                changes.append('added load class %s' % CLASS_NAME[cls])
            mwh, kva = x.values(P_MWH), x.values(P_KVA)
            if mwh == [5200] and kva == [13000] and legacy[0] in LUA_MWH and x.values(P_TARGETS)[-1] not in GAME_MWH:
                m = LUA_MWH[legacy[0]]
                k = int(math.floor(2.5 * m + 0.5))
                x.set(P_MWH, 0x03, [m], False)
                x.set(P_KVA, 0x03, [k], False)
                changes.append('MWh 5200 / kVA 13000 (copied) -> MWh %d (NEON_LUA) / kVA %d (2.5 x MWh)' % (m, k))
        tg = x.values(P_TARGETS)
        if len(tg) == 2 and tg[1] in GAME_MWH:
            m = GAME_MWH[tg[1]]
            k = int(math.floor(2.5 * m + 0.5))
            if x.values(P_MWH) != [m] or x.values(P_KVA) != [k]:
                old_m, old_k = (x.values(P_MWH) or [None])[0], (x.values(P_KVA) or [None])[0]
                x.set(P_MWH, 0x03, [m], False)
                x.set(P_KVA, 0x03, [k], False)
                if (old_m, old_k) == (5200, 13000): old_m, old_k = '5200', '13000 (copied)'
                changes.append('MWh %s / kVA %s -> MWh %d (power produced by the lot, from SC4NEON.log) / kVA %d (2.5 x MWh)' % (old_m, old_k, m, k))
        if groups != list(x.values(P_OG, [])):
            x.set(P_OG, 0x03, groups, True)
        if e.i in UI_REPOINT:
            new_ui, why = UI_REPOINT[e.i]
            old = x.values(P_UI)
            x.set(P_UI, 0x03, [new_ui], False)
            changes.append('query UI %08X -> %08X (%s)' % (old[0], new_ui, why))
        if changes:
            e.data = x.to_bytes()
            note(name, 'patch %08X "%s": %s' % (e.i, title, '; '.join(changes)))

# ------------------------------------------------------------------ F. third-party lots without a load class (SC4NEON.log, 25 Oct 2026)
# Occupant groups as the game loaded them, plus the load class. A patch replaces the whole OccupantGroups list.
THIRD_PARTY = [
    ('NEON_Nuclear_Power_Plant.dat', 'Patch NEON: BD VVER-1000 Pressurized Reactor', 0xC8DBCCBA, 0xD5A0F22C,
     [0x1004, 0x1400, 0x1403, 0x1928, 0xA945A10D, 0xB5C00EF1, 0xBB350079], OG_B, None),
    ('NEON_Wind_Power_Plant.dat', 'Patch NEON: SG GooberGen Wind Power Inc', 0x56BDD705, 0x77787F0F,
     [0x1004, 0x1400, 0xB5C00EF1, 0xB5C001FF, 0xC78E0054], OG_I, None),
    ('NEON_Geothermal_Power_Plant.dat', 'Patch NEON: SG GeoThermalGenerator', 0xB5C52C45, 0x56FC8C73,
     [0x1004, 0x1400, 0xB5C00EF1, 0xB5C00158, 0xB5C0017C, 0xB5C001FF, 0x1F221780], OG_B, 21125),
    # CAM Electric Generator (CAM_Maxis_Building_Extended.dat): 800 MWh, Maxis plant type 3 (natural gas) -> NEON natural gas
    # generator, Peak, own group BB350101 (NG generators #2) and own query BB353101. Not conditional: always available.
    ('NEON_Generator.dat', 'Patch NEON: CAM Electric Generator', 0x55FDAF8F, 0x561E640A,
     [0x1004, 0x1400, 0xBB350101, OG_GEN, OG_GAS], OG_P, 2000),
]
import zlib
template = None
for e in pk['NEON_Geothermal_Power_Plant.dat'].entries:
    if e.t == COHORT:
        template = e.data
        break
for fname, title, tg, ti, groups, cls, kva in THIRD_PARTY:
    x = Exemplar(template)
    x.props = [pr for pr in x.props if pr.id in (P_NAME, P_TARGETS)]
    x.set(P_NAME, 0x0C, [title], True)
    x.set(P_TARGETS, 0x03, [tg, ti], True)
    x.set(P_OG, 0x03, groups + [cls], True)
    if kva is not None:
        x.set(P_KVA, 0x03, [kva], False)
    if ti == 0xD5A0F22C:
        x.set(P_UI, 0x03, [0xBB353079], False)
    if ti == 0x561E640A:
        x.set(P_UI, 0x03, [0xBB353101], False)
        x.set(P_MWH, 0x03, [800], False)
    inst = zlib.crc32(b'NEON patch %08X %08X' % (tg, ti)) & 0xFFFFFFFF
    pk[fname].add(COHORT, 0xB03697D1, inst, x.to_bytes())
    note(fname, 'new patch %08X "%s" for %08X/%08X: load class %s%s' % (inst, title, tg, ti, CLASS_NAME[cls],
         '' if kva is None else ', kVA %d (2.5 x MWh)' % kva))

# ------------------------------------------------------------------ F2. CAM Electric Generator: own query BB353101
gen_ui = pk['NEON_UI_Generator_Files.dat']
src_ui = next(e for e in gen_ui.entries if e.t == UI and e.g == UI_GROUP and e.i == 0xBB353100)
ui_text = src_ui.data.decode('latin-1')
assert ui_text.count('bb350900') == 1 and ui_text.count('bb350100') == 1
gen_ui.add(UI, UI_GROUP, 0xBB353101, ui_text.replace('bb350900', 'bb350901').replace('bb350100', 'bb350101').encode('latin-1'))
note('NEON_UI_Generator_Files.dat', 'new query UI BB353101 for the CAM Electric Generator (copy of BB353100 reading mwh_rating.ID_BB350101)')
lt_idx = ltext_index()
for old_i, new_i in ((0xBB350900, 0xBB350901), (0xBB350100, 0xBB350101)):
    fname, src = lt_idx[(TXT_GROUP, old_i)]
    t = ltext_decode(src.data)[0]
    assert 'ID_BB350100' in t
    pk[fname].add(LTEXT, TXT_GROUP, new_i, ltext_encode(t.replace('ID_BB350100', 'ID_BB350101')))
    note(fname, 'new LTEXT %08X %08X (copy of %08X for the CAM Electric Generator)' % (TXT_GROUP, new_i, old_i))

# ------------------------------------------------------------------ G. nuclear plants (BurroDiablo lots checked 25 Oct 2026)
# VVER-1000 (D5A0F22C): new NEON group BB350079 (Large Fission #2, counted by SC4NEON.dll) and its own query UI BB353079,
# a copy of the BurroDiablo one (BB353080) that reads mwh_rating.ID_BB350079.
fission_ui = pk['NEON_UI_Nuclear_Fission_Files.dat']
src_ui = next(e for e in fission_ui.entries if e.t == UI and e.g == UI_GROUP and e.i == 0xBB353080)
ui_text = src_ui.data.decode('latin-1')
assert ui_text.count('bb350880') == 1 and ui_text.count('bb350080') == 1
fission_ui.add(UI, UI_GROUP, 0xBB353079, ui_text.replace('bb350880', 'bb350879').replace('bb350080', 'bb350079').encode('latin-1'))
note('NEON_UI_Nuclear_Fission_Files.dat', 'new query UI BB353079 for the VVER-1000 (copy of BB353080 reading mwh_rating.ID_BB350079)')
lt_idx = ltext_index()
for old_i, new_i in ((0xBB350880, 0xBB350879), (0xBB350080, 0xBB350079)):
    fname, src = lt_idx[(TXT_GROUP, old_i)]
    t = ltext_decode(src.data)[0]
    assert 'ID_BB350080' in t
    pk[fname].add(LTEXT, TXT_GROUP, new_i, ltext_encode(t.replace('ID_BB350080', 'ID_BB350079')))
    note(fname, 'new LTEXT %08X %08X (copy of %08X for the VVER-1000)' % (TXT_GROUP, new_i, old_i))
# BurroDiablo "Massive Yield" reactor (542CA54B): MWh 637,000 and kVA 1,592,500 in the lot are already correct (2.5 x MWh).

# ------------------------------------------------------------------ H. flavour values of the query windows
# The texts called game.cam_get_*(), which no file defines: the token failed and the windows showed "#math.random()#".
# They now call neon_cam_value(name, max) from NEON_LUA (uses game.cam_get_<name> if another mod defines it).
CAM_VALUES = {0x2000007E: ('latefuel', 3), 0x20000081: ('stuckmirror', 4), 0x20000082: ('birdcarcasses', 12),
              0x20000083: ('daysaccidents', 365), 0x20000084: ('bodyparts', 2), 0x20000085: ('sulfursmell', 15),
              0x20000086: ('nuclearwaste', 3), 0x20000087: ('fuelspills', 5), 0x20000088: ('ctdlogged', 9),
              0x20000089: ('batterymeltdown', 1), 0x2000008A: ('birdslines', 40), 0x2000008C: ('fusesblown', 6)}
lt_idx = ltext_index()
for inst, (name, mx) in CAM_VALUES.items():
    fname, e = lt_idx[(TXT_GROUP, inst)]
    old = ltext_decode(e.data)[0]
    assert old == '#game.cam_get_%s()#' % name, (hex(inst), old)
    e.data = ltext_encode('#neon_cam_value("%s", %d)#' % (name, mx))
    note(fname, 'LTEXT %08X %08X: %s -> neon_cam_value("%s", %d) (uses the CAM function, with a fallback if CAM is missing or returns nil)' % (TXT_GROUP, inst, old, name, mx))

# ------------------------------------------------------------------ J. 10 MVA transmission: only the NEON lot 88630077
# The Maxis Power Substation of the mod is the NEON lot (section K). The patch and the menu icon for Takingyouthere's
# Transformer Substation / KK override (B2682B4A/64A800CD) are removed, so those packs are no longer NEON lots.
tx = pk['NEON_Transmission.dat']
for e in list(tx.entries):
    if e.t == COHORT and (Exemplar(e.data).values(P_TARGETS) or [0, 0])[1] == 0x64A800CD:
        tx.remove(e)
        note('NEON_Transmission.dat', 'removed patch %08X "Patch NEON: Maxis Power Substation" (Takingyouthere / KK 64A800CD): '
             'replaced by the NEON lot 88630077' % e.i)
    elif e.t == 0x856DDBAC and e.i == 0x64A800CD:
        tx.remove(e)
        note('NEON_Transmission.dat', 'removed menu icon 856DDBAC/%08X/64A800CD (it overrode the Takingyouthere / KK lot icon)' % e.g)

# ------------------------------------------------------------------ L. text review (26 Oct 2026)
# Every LTEXT of the mod was read and checked against NEON_LUA, the exemplar patches and SC4NEON.dll.
G_RW, G_UI = 0x6A231EA4, TXT_GROUP
LINK = '<a href="#link_id#game.tool_plop_building(hex2dec(\'%s\'))">%s</a>'
TEXT_EDITS = [
    # --- links to lots that are not NEON lots
    (G_RW, 0x6A4F94F9, "hex2dec('64A800CD')", "hex2dec('88630077')", 'link to the Takingyouthere / KK 10 MVA station -> NEON Maxis Power Substation 88630077'),
    (G_RW, 0xBB352834, "hex2dec('64A800CD')", "hex2dec('88630077')", 'link to the Takingyouthere / KK 10 MVA station -> NEON Maxis Power Substation 88630077'),
    (G_RW, 0xBB3528C0, "go beyond the smaller <a href=\"#link_id#game.tool_plop_building(hex2dec('774A9DB5'))\">6.5 MW Coal Power Plants</a>",
     "go beyond the smaller <a href=\"#link_id#game.tool_plop_building(hex2dec('DFCF65CD'))\">2 MW Coal Power Plants</a>",
     'linked the AMPS-only 6.5 MW Coal Plant (774A9DB5): now the NEON 2 MW Coal Power Plant (DFCF65CD)'),
    (G_RW, 0xBB3529A4, "build a <a href=\"#link_id#game.tool_plop_building(hex2dec('C9FBC2CD'))\">6 MW Natural Gas Power Plant</a>",
     "build a <a href=\"#link_id#game.tool_plop_building(hex2dec('C9FBC2CD'))\">6.5 MW Natural Gas Power Plant</a>", 'plant name 6 MW -> 6.5 MW (as its title)'),
    (G_RW, 0xBB3529A4, "For less air pollution than the <a href=\"#link_id#game.tool_plop_building(hex2dec('956C4C30'))\">4.5 MW Oil Plants</a> puts out",
     "For less air pollution than our <a href=\"#link_id#game.tool_plop_building(hex2dec('65FC4DF7'))\">diesel generators</a> put out",
     'linked the AMPS-only 4.5 MW Oil Plant (956C4C30): now the NEON Mobile Diesel Generator'),
    (G_RW, 0xEA4F9311, "starting with the <a href=\"#link_id#game.tool_plop_building(hex2dec('0D3967A7'))\">25 kVA Pole-Mount</a> for left or "
     "<a href=\"#link_id#game.tool_plop_building(hex2dec('2D39CE63'))\">right-hand side of the road</a>, then the ",
     'starting with the ', 'removed the 25 kVA Pole-Mount transformers (0D3967A7 / 2D39CE63): not NEON lots, the links did nothing'),
    (G_RW, 0xEA4F9311, "build a <a href=\"#link_id#game.tool_plop_building(hex2dec('2D2F6722'))\">Front Office</a>",
     "build a <a href=\"#link_id#game.tool_plop_building(hex2dec('5DD19A13'))\">Front Office</a>",
     '"Front Office" linked the 250 kVA transformer (2D2F6722): now the Front Office 5DD19A13'),
    (G_RW, 0xEA4F9311, 'that its hooked up', "that it's hooked up", 'typo'),
    (G_RW, 0xEA4F9311, 'Glad to know  you', 'Glad to know you', 'double space'),
    (G_RW, 0xBB352A02, "hex2dec(' DDDCF85C ')", "hex2dec('DDDCF85C')", 'spaces inside the building id of the link'),
    (G_RW, 0xBB352A02, "hex2dec(' 5DE732E3 ')", "hex2dec('5DE732E3')", 'spaces inside the building id of the link'),
    (G_RW, 0xBB352A03, "hex2dec(' 6DE128C6 ')", "hex2dec('6DE128C6')", 'spaces inside the building id of the link'),
    (G_RW, 0xBB352A03, "hex2dec(' 9DED3678 ')", "hex2dec('9DED3678')", 'spaces inside the building id of the link'),
    (G_RW, 0xBB352A04, "hex2dec(' AD6EBF67 ')", "hex2dec('AD6EBF67')", 'spaces inside the building id of the link'),
    (G_RW, 0xBB352A04, 'Headquarters/a>', 'Headquarters</a>', 'broken HTML: the link was never closed'),
    # --- facts that do not match NEON
    (G_RW, 0x4AA6DC6E, "Best of all, the plant can load follow for when we need power at peak times of the day! Unfortunately, it's a bit more "
     "expensive per megawatt than other peak power plants, but we can export the excess to help pay for the costs!",
     "Best of all, it delivers a huge, steady supply of clean Base Load power around the clock! Unfortunately, it's quite expensive per "
     "megawatt, so we'll want to make good use of every bit of its output!",
     'fusion is a Base Load plant in NEON (AMPS: Peak); power sales come from Peak plants only'),
    (0x13AA0372, 0x542CA54B, 'These monstrous facilities are of a newer design that can load follow, making them a unique type of fission plant that '
     'can meet ALL power needs... if you can afford it.',
     'These monstrous facilities produce an enormous, steady stream of Base Load power, enough for a whole region of cities... '
     'if you can afford it.', 'BurroDiablo is a Base Load plant in NEON (AMPS: load following Peak)'),
    (0x13AA0372, 0x542CA54B, 'Plant Type: Large Peak Load', 'Plant Type: Large Base Load', 'load class as in the NEON patch (Base)'),
    (G_RW, 0xBB352480, '- 112 MW Fission Plant or greater (', '- Large Fission Plant besides the 25 MW Fission Plant (',
     'the 112 MW Fission Plant is an AMPS-only lot; the condition counts any large fission plant except the Maxis one (VVER-1000)'),
    (G_RW, 0xBB352925, "What power plant's CAN'T you build? Well, only three come to mind and they're all nuclear: the 75 MW Fusion Power Plant, "
     "the 112 MW Fission Power Plant, and the 1.2 Gigawatt Fission Power Facility. Just remember, if you build more distribution substations, "
     "you can have more than one of these... and just two of them means every plant but the big one! Something to reach for!",
     "What power plants CAN'T you build? Only the nuclear giants: the 25 MW Fission Power Plant, the 75 MW Fusion Power Plant and the "
     "big fission facilities. Just remember, if you build more distribution substations, you can have more than one of these... and a few "
     "of them working together can carry even those! Something to reach for!",
     'listed the AMPS-only 112 MW Fission Plant; in NEON (kVA = 2.5 x MWh) the plants above 90 MVA are the nuclear ones'),
    (G_RW, 0xBB352926, 'can handle the power output of all but the three largest fission facilities alone',
     'can handle the power output of all but the largest nuclear plants alone', 'the three AMPS fission facilities are not all in NEON'),
    (G_RW, 0xBB352960, 'but that means 5,000 megawatt-hours of clean power', 'but that means 12,500 megawatt-hours of clean power',
     'NEON wind turbine: 500 MWh x 25 turbines (AMPS: 200 MWh)'),
    (G_RW, 0xBB3528D0, 'and it provides almost as much power as the Coal Plant!', 'and it provides even more power than the Coal Plant!',
     'NEON: W2E 8,500 MWh, 10 MW Coal 7,500 MWh'),
    (G_RW, 0xBB352870, 'Pumping out almost five times the power of the smallest geothermal plants',
     'Pumping out more than ten times the power of the 4 MW Geothermal Plant', 'NEON: 25,000 MWh vs 2,200 MWh'),
    (G_RW, 0xBB352870, 'What we need is a <a', 'What we need is an <a', 'grammar (an 8 MW)'),
    (G_RW, 0xBB352871, 'With just as much power output as a 10 MW Coal Power Plant', 'With nearly as much power output as a 10 MW Coal Power Plant',
     'NEON: 6,000 MWh vs 7,500 MWh'),
    (G_RW, 0xBB352971, 'With more than double the power output of the 2 MW model, these units can really pour out the power.',
     'These units can really pour out the power.', 'the 2 MW Geothermal Plant is an AMPS-only lot'),
    (0x0A554AE0, 0x0A5EA690, 'cost per megawatt is almost half that of the Clean version, but still more expensive than any other Base Load plant.',
     'it burns garbage instead of fuel, but its cost per megawatt is higher than any other Base Load plant.',
     'the Clean Waste to Energy Plant is an AMPS-only lot'),
    (G_RW, 0xBB354300, 'Base Load plants, which are our wood, coal, waste, geothermal, and nuclear plants,',
     'Base Load plants, which are our coal, biomass, waste, geothermal, hydroelectric, and nuclear plants,',
     'NEON Base Load classes (no wood plants in NEON)'),
    (G_UI, 0x100000A0, '(Wind, Solar)', '(Solar, Wind, Tidal)', 'NEON Intermediate classes'),
    (G_UI, 0x100000A1, '(Solar, Wind)', '(Solar, Wind, Tidal)', 'NEON Intermediate classes'),
    (G_UI, 0x100000A3, '(Geothermal, Fission, Wood, Coal, Waste, Hydroelectric)', '(Coal, Biomass, Geothermal, Waste, Hydroelectric, Fission, Fusion)',
     'NEON Base Load classes'),
    (G_UI, 0x100000A4, '(Oil, Natural Gas, Load-Following Fission, Fusion)', '(Oil, Natural Gas, Microwave)', 'NEON Peak classes'),
    (G_UI, 0x100000A5, '(Oil, Natural Gas, Load-Following Fission, Fusion)', '(Oil, Natural Gas, Microwave)', 'NEON Peak classes'),
    (G_UI, 0x100000FF, 'not directly supported by AMPS', 'not directly supported by NEON', 'mod name'),
    # --- capacity shown from the AMPS property 0x4AA60EBC, which no NEON exemplar has: the NEON patches carry kVA in 0xE652E51F
    *[(g, i, '#d:4AA60EBC#', '#d:E652E51F#', 'kVA read from 0xE652E51F (NEON patch) instead of the AMPS property 0x4AA60EBC (empty in NEON)')
      for g, i in ((0x0A554AE0, 0x3A556B6C), (0x0A554AE0, 0xB4B9AED9), (0x0A554AE0, 0xB4C17F2E), (0x59561805, 0xF96D171C),
                   (0x7F7D0785, 0xDFCF65CD), (0xC8DBCCBA, 0x70F4A14F), (0x7CC07882, 0x690A0D1A))],
    (0xBBFCE7B9, 0x6DD69839, 'Distribution Capacity Used:', 'Transmission Capacity Used:', 'Sim Gideon is a Large Power Plant (transmission)'),
    (0x0A554AE0, 0xCA5EA690, 'Garbage:#d:C8ED2D84#', 'Garbage: 20', 'Garbage showed the water property (value 20 as in AMPS)'),
    # --- typos and wording
    (G_RW, 0xBB352832, 'THIER', 'THEIR', 'typo'),
    (G_RW, 0xBB352825, "set's people's nerves", "sets people's nerves", 'typo'),
    (G_RW, 0xBB352835, 'than the 5 MW substation', 'than the 5 MVA substation', 'unit'),
    (G_RW, 0xBB352835, 'than rest of the smaller stations', 'than the rest of the smaller stations', 'grammar'),
    (G_RW, 0xBB352838, 'a electronics geek', 'an electronics geek', 'grammar'),
    (G_RW, 0xBB352921, 'a pair of these it will support', 'a pair of these will support', 'grammar'),
    (G_RW, 0xBB352841, '1.9 MW Tesla Powerpack</a>', '1.9 MWh Tesla Powerpack</a>', 'unit (as its title)'),
    (G_RW, 0xBB352842, '>1.9 MW</a>', '>1.9 MWh</a>', 'unit (as its title)'),
    (G_RW, 0xBB352843, '>1.9 MW</a>', '>1.9 MWh</a>', 'unit (as its title)'),
    (G_RW, 0xBB352950, "(when its not raining)", "(when it's not raining)", 'typo'),
    (G_RW, 0xBB352403, '945 kW Diesel Generator is not available.', '945 kW Container Diesel Generator is not available.', 'name as its title'),
    (G_RW, 0xAA4F935C,'before the plants need replaced', 'before the plants need to be replaced', 'grammar'),
    (G_RW, 0xEA501BF2, "your citizen's offices", "your citizens' offices", 'grammar'),
    (G_RW, 0xBB352524, '#unlock_variables.TRANS_SUBSTATION_60_MVA_S_BRIDGE#)', '#unlock_variables.TRANS_SUBSTATION_60_MVA_S_BRIDGE#',
     'stray ")" (also in AMPS)'),
    (0x0A554AE0, 0xB4B9AED9, 'so expensive to build that the are only', 'so expensive to build that they are only', 'typo'),
    (0xF38748F8, 0xB694726D, 'isolated locals', 'isolated locales', 'typo'),
]
TEXT_REPLACE = {   # whole texts
    (G_UI, 0x100000A2): ('Percent of used power that is from Base sources (Coal, Biomass, Geothermal, Waste, Hydroelectric, Fission, Fusion)\r\n',
                         'was a copy of the next tooltip (total MWh) instead of the percentage'),
    (G_UI, 0x100000C4): ('Total power produced by all Base Load sources in MWh per month\r\n', 'tooltip was cut to "Total power"'),
    (G_UI, 0x100000C8): ('Total Net Base Power generated that is being used in MWh per month\r\n',
                         'tooltip showed a line of the "independent power plants" notice ("the fact that Allied Municipal Power")'),
    (G_RW, 0xBB352120): ('10 MVA Maxis Power Substation', 'title of the NEON lot 88630077 (was "10 MVA Transmission Station (Left)", the KK variant)'),
}
TEXT_NEW = {   # missing texts: the 10 MVA reward (transmission_station_hex_id.MVA_10_1) used them, NEON never had them
    (G_RW, 0xBB352520): ('NEON_High_Substation_Locale_en.dat',
        '10 MVA Maxis Power Substation is not available.\r\nRequirements:\r\n'
        '    - Unused Distribution Capacity: #kva_rating.ID_BB350120# kVA\r\n'
        '----------------------------------------------------------\r\n'
        '    - #run_grid_balance_variables ("D")# kVA Distribution Capacity Available'),
    (G_RW, 0xBB352920): ('NEON_High_Substation_Locale_en.dat',
        "OK, so you built up a decent number of Distribution Substations and didn't immediately load them up with more Small Power "
        "Plants, so now we can set aside some of that capacity for some serious power. The " + LINK % ('88630077', '10 MVA Maxis Power Substation') +
        " steps the output of a power plant up to high voltage and will open the door to bigger and better power plants. Keep in mind "
        "though that a Large Power Plant needs transmission capacity at least equal to its rating, so most of them need <b>two</b> or more "
        "of these stations, and the really big ones even more.<p>Once we have these down and learn how to balance power output from at "
        "least one Large Power Plant, we can look into getting access to even larger transmission stations. Until then, put them near "
        "our power plants and run high-voltage lines from them to our distribution substations. It's a compact little station, Mayor... "
        "the Maxis engineers really knew what they were doing!"),
}
lt_idx = ltext_index()
for g, i, old, new, why in TEXT_EDITS:
    fname, e = lt_idx[(g, i)]
    text = ltext_decode(e.data)[0]
    assert text.count(old) == 1, ('%08X %08X' % (g, i), old, text.count(old))
    e.data = ltext_encode(text.replace(old, new))
    note(fname, 'LTEXT %08X %08X: %s' % (g, i, why))
for (g, i), (new, why) in TEXT_REPLACE.items():
    fname, e = lt_idx[(g, i)]
    old = ltext_decode(e.data)[0]
    e.data = ltext_encode(new)
    note(fname, 'LTEXT %08X %08X: "%s" -> "%s" (%s)' % (g, i, old.strip()[:60], new.strip()[:60], why))
for (g, i), (fname, t) in TEXT_NEW.items():
    assert (g, i) not in lt_idx
    pk[fname].add(LTEXT, g, i, ltext_encode(t))
    note(fname, 'new LTEXT %08X %08X (missing text of the 10 MVA reward MVA_10_1, adapted from AMPS for the NEON lot 88630077)' % (g, i))
# the item description of Takingyouthere's lot (64A800CD) is no longer a NEON lot (section J)
fname, e = lt_idx[(0xC8DBCCBA, 0x64A800CD)]
pk[fname].remove(e)
note(fname, 'removed LTEXT C8DBCCBA 64A800CD: description of the Takingyouthere / KK 10 MVA station, no longer a NEON lot')

# ------------------------------------------------------------------ M. plant names in MW from the NEON values
# AMPS named the plants by kVA x 0.8 (power factor, as the substations: 10 MVA = 8 MW) of its own rescaled ratings. NEON keeps
# the game power, so the names now follow the same rule on the NEON ratings: MW = kVA x 0.8 / 1000 = MWh / 500 (kVA = 2.5 x MWh).
PLANT_NAMES = [   # (old, new, MWh per month in NEON)
    ('240 kW Mobile Diesel', '3 MW Mobile Diesel', 1500), ('945 kW Container Diesel', '800 kW Container Diesel', 400),
    ('180 kW Natural Gas Generator', '150 kW Natural Gas Generator', 75), ('25 kW PV Panel', '200 kW PV Panel', 100),
    ('370 kW PV Power Plant', '5 MW PV Power Plant', 2500), ('2.5 MW Solar Thermal', '16 MW Solar Thermal', 8000),
    ('4 MW Geothermal', '4.4 MW Geothermal', 2200), ('8 MW Geothermal', '50 MW Geothermal', 25000),
    ('10 MW Geothermal', '12 MW Geothermal', 6000), ('15 and 25 MW Clean Coal plants', '12 MW Clean Coal plant', 6000),
    ('15 MW Clean Coal', '12 MW Clean Coal', 6000), ('35 MW Clean Coal', '42 MW Clean Coal', 21000),
    ('10 MW Coal', '15 MW Coal', 7500), ('2 MW Coal', '2.5 MW Coal', 1250), ('15 MW Oil', '23 MW Oil', 11600),
    ('34 MW Natural Gas', '59 MW Natural Gas', 29500), ('6.5 MW Natural Gas', '10 MW Natural Gas', 5200),
    ('25 MW Fission', '87 MW Fission', 43400), ('75 MW Fusion', '184 MW Fusion', 92100),
    ('9 MW Waste to Energy', '17 MW Waste to Energy', 8500), ('1.2 GW Fission', '1.3 GW Fission', 637000),
]
name_re = re.compile(r'(?<![\d.])(' + '|'.join(re.escape(o) for o, _, _ in sorted(PLANT_NAMES, key=lambda x: -len(x[0]))) + r')')
name_map = {o: n for o, n, _ in PLANT_NAMES}
renamed = {}
for name, p in pk.items():
    for e in p.entries:
        if e.t != LTEXT:
            continue
        text = ltext_decode(e.data)[0]
        new = name_re.sub(lambda m: name_map[m.group(1)], text)
        if new != text:
            e.data = ltext_encode(new)
            found = sorted(set(name_re.findall(text)))
            for f in found:
                renamed[f] = renamed.get(f, 0) + 1
            note(name, 'LTEXT %08X %08X: plant names %s' % (e.g, e.i, ', '.join('"%s" -> "%s"' % (f, name_map[f]) for f in found)))
for o, n, mwh in PLANT_NAMES:
    assert renamed.get(o), o
    note('(all locale files)', 'plant name "%s" -> "%s" (%s MWh x 2.5 kVA x 0.8 = %.1f MW), %d texts' % (o, n, format(mwh, ','), mwh / 500, renamed[o]))
# comparisons in the texts that the NEON values make wrong
lt_idx = ltext_index()
SIZE_EDITS = [
    (0x0A554AE0, 0x3A556B6C, 'The 2nd largest geothermal plant', 'The largest geothermal plant', 'SM2 Geothermal 25,000 MWh is the largest in NEON'),
    (0x0A554AE0, 0xB4B9AED9, 'The largest geothermal plant', 'The 2nd largest geothermal plant', 'PEG Geothermal 6,000 MWh'),
    (0x59561805, 0xF96D171C, 'for twice the per megawatt cost and 3.5 times the power.', 'for twice the per megawatt cost and nearly 3 times the power.',
     '21,000 vs 7,500 MWh'),
    (0xC8DBCCBA, 0x70F4A14F, 'generate 3 times the power, but', 'generate more power than the Maxis Natural Gas plant, but', '6,000 vs 5,200 MWh'),
    (0xBBFCE7B9, 0x6DD69839, 'Produces 15% more power than the largest Oil Power Plant', 'Produces two and a half times the power of the largest Oil Power Plant',
     '29,500 vs 11,600 MWh'),
    (G_RW, 0xBB352803, 'telling me about something similar, but bigger.', 'telling me about something similar, but built for remote camps.',
     'the Container Diesel (400 MWh) is smaller than the Mobile Diesel (1,500 MWh) in NEON'),
    (G_RW, 0xBB352803, "it's a shame that we don't have something like that, a bigger generator to meet",
     "it's a shame that we don't have something like that, another generator to meet", 'as above'),
    (G_UI, 0x100000F5, 'that is rated at less than 8 MW', 'that is a Small Power Plant (powered through distribution substations)',
     'NEON sorts Small / Large by the plant group, not by an 8 MW threshold'),
    (G_UI, 0x100000F6, 'that is rated at 8 MW or greater', 'that is a Large Power Plant (powered through transmission stations)', 'as above'),
]
for g, i, old, new, why in SIZE_EDITS:
    fname, e = lt_idx[(g, i)]
    text = ltext_decode(e.data)[0]
    assert text.count(old) == 1, ('%08X %08X' % (g, i), old)
    e.data = ltext_encode(text.replace(old, new))
    note(fname, 'LTEXT %08X %08X: %s' % (g, i, why))

# ------------------------------------------------------------------ N. power company: SINGO (SimNation Independent Grid Operator)
# The in-game power company buildings were "AMPS ..." (Allied Municipal Power of Simtropolis, the AMPS mod). NEON calls the grid
# operator SINGO. Kept: the AMPS credits and the AMPS licence text (attribution required by CC BY-NC-SA) and the Lua variable names.
office_re = re.compile(r'\bAMPS\b(?![_A-Z])')
for (g, i), (fname, e) in sorted(ltext_index().items()):
    if fname != 'NEON_Office_Locale_en.dat':
        continue
    text = ltext_decode(e.data)[0]
    parts = re.split(r'(#[^#]*#)', text)          # never inside #...# tokens
    new = ''.join(s if s.startswith('#') and s.endswith('#') and len(s) > 1 else office_re.sub('SINGO', s) for s in parts)
    if new != text:
        e.data = ltext_encode(new)
        note(fname, 'LTEXT %08X %08X: AMPS -> SINGO (%d)' % (g, i, len(office_re.findall(''.join(s for s in parts if not s.startswith('#'))))))
lt_idx = ltext_index()
for (g, i), old, new, why in (
        ((0x1DC6743A, 0xAD6EBF67), 'The Corporate Headquarters for SINGO.', 'The Corporate Headquarters of SINGO, the SimNation Independent Grid Operator.',
         'full name of SINGO'),
        ((G_UI, 0x10000008), 'the fact that Allied Municipal Power', 'the fact that the grid operator SINGO', 'company of the office window'),
        ((G_UI, 0x10000011), 'AMPS: Allied Municipal Power of Simtropolis\r\nCreated by Roberta Elder (RobertaME)',
         'SINGO: SimNation Independent Grid Operator\r\nNEON by Ulisse Wolf, based on AMPS (Allied Municipal Power of Simtropolis)\r\n'
         'AMPS created by Roberta Elder (RobertaME)', 'credits: SINGO / NEON, the AMPS credits kept')):
    fname, e = lt_idx[(g, i)]
    text = ltext_decode(e.data)[0]
    assert text.count(old) == 1, ('%08X %08X' % (g, i), old)
    e.data = ltext_encode(text.replace(old, new))
    note(fname, 'LTEXT %08X %08X: %s' % (g, i, why))

# ------------------------------------------------------------------ O. advisor links
# game.tool_plop_building() takes a LOT configuration IID. The links to the CAM power plants use the CAM building IID,
# which is also the IID of its CAM lot (CAM_Power_Garbage_Buildings.dat, lots moved off the Maxis lot IIDs on 25 Oct 2026),
# so they stay as they are. Third-party lots: lot IID = building IID (the Lot Resource Key AMPS gave them).

# ------------------------------------------------------------------ K. NEON lot: 2x2 Maxis Power Substation (88630077)
# Rebuilt from Takingyouthere's Transformer Substation and corrected by fix_substation_lot.py (kVA 10,000, NEON query
# BB353120, pole back in its place, new description). Needs Takingyouthere's models and wire props (see the readme).
EXTRA = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'extra')
lot_dir = os.path.join(DST, 'CAM', '0 Expansion', 'NEON', '1 Power Features', '2 Substation', 'Transmission')
os.makedirs(lot_dir, exist_ok=True)
for f in sorted(os.listdir(EXTRA)):
    if f.lower().endswith('.sc4lot'):
        shutil.copy2(os.path.join(EXTRA, f), os.path.join(lot_dir, f))
        # item description in the NEON format of the other substations (text review, section L)
        lotpk = Package(os.path.join(lot_dir, f))
        d = lotpk.get(LTEXT, 0x55FDAF8F, 0x88630077)
        d.data = ltext_encode(
            'Monthly Cost:    #m:ea54d286#\r\n\r\n'
            'The smallest Transmission Station, it steps up to 10 MVA (8 MW) of power plant output to high voltage and has Maxis power '
            'line hookups. Transmission Stations allow Large Power Plants and need Distribution Substations.\r\n'
            'Created by Takingyouthere\r\nRe-lotted for NEON\r\n\r\n'
            'Lot Size: 2x2 -- Bulldoze: #m:099AFACD#\r\nProvides no Jobs\r\nGarbage: 0 -- Water: #d:C8ED2D84#\r\n\r\nTransmission Station')
        lotpk.save(os.path.join(lot_dir, f))
        note(f, 'item description LTEXT 55FDAF8F/88630077 rewritten in the format of the other NEON substations (cost, size, jobs, garbage, water)')
        note(f,'new NEON lot in 1 Power Features/2 Substation/Transmission: 10 MVA transmission substation '
                '(NEON group HV Transformers 0xED378A8E, kVA 10,000, query BB353120, NEON icon, conditional: NEON reward MVA_10_1)')

# ------------------------------------------------------------------ save
for name, p in pk.items():
    p.save(path_of[name])   # unchanged files are written back byte-identical

with open(os.path.join(DST, 'NEON_fixes_log.md'), 'w', encoding='utf-8') as f:
    f.write('# NEON fixes applied\n\n| File | Change |\n| --- | --- |\n')
    for file, what in log:
        f.write('| %s | %s |\n' % (file, what.replace('|', '/')))
print(len(log), 'changes')
