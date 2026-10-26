"""Re-checks a NEON mod folder: query UIs -> texts, patches -> UIs, every LTEXT Lua token (DLL mode), duplicates."""
import json, os, re, sys, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dbpfedit import Package, Exemplar, ltext_decode
root = sys.argv[1]
GAME_GROUPS = {0x46A006B0, 0x6A231EAA, 0xEA5524EB, 0x227A224B, 0x03501234}   # Maxis UI images and texts
res, lt, uis, patches, dups = set(), {}, {}, [], []
for dp, _, fn in os.walk(root):
    for f in fn:
        if not f.endswith('.dat'): continue
        p = Package(os.path.join(dp, f))
        dups += [(f, k) for k in p.duplicates()]
        for e in p.entries:
            res.add(e.key)
            if e.t == 0x2026960B: lt['%08X_%08X' % (e.g, e.i)] = (f, ltext_decode(e.data)[0], ltext_decode(e.data)[1])
            if e.t == 0 and e.g == 0x96A006B0: uis[e.i] = (f, e.data.decode('latin-1'))
            if e.t == 0x05342861:
                x = Exemplar(e.data)
                if x.values(0x0062E78A): patches.append((f, e.i, x))
problems = []
for uid, (f, s) in sorted(uis.items()):
    for g, i in re.findall(r'captionres=\{([0-9a-f]+),([0-9a-f]+)\}', s):
        g, i = int(g, 16), int(i, 16)
        if g and g not in GAME_GROUPS and '%08X_%08X' % (g, i) not in lt:
            problems.append('UI %08X (%s): text %08X %08X missing' % (uid, f, g, i))
for f, inst, x in patches:
    ui = x.values(0x2A499F85)
    if ui and ui[0] not in uis: problems.append('patch %08X (%s): query UI %08X missing' % (inst, f, ui[0]))
for f, k in dups: problems.append('duplicate entry %s %08X %08X %08X' % ((f,) + k))
non_utf16 = [k for k, v in lt.items() if not v[2]]
if non_utf16: problems.append('LTEXT without UTF-16 header: %d' % len(non_utf16))
json.dump({k: (v[0], v[1]) for k, v in lt.items()}, open('ltext/all.json', 'w'))
print('\n'.join(problems) or 'references: no problems')
print('UIs %d, LTEXTs %d, patches %d' % (len(uis), len(lt), len(patches)))
