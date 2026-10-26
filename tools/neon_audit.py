"""NEON exemplar audit - checks .dat files the same way SC4NEON.dll does in game.

usage: python neon_audit.py <file or folder> [more...]   (scans *.dat, *.sc4lot, *.sc4desc recursively)

Exemplar patches (cohorts with property 0x0062E78A) are applied to their target exemplars first,
like SC4ResourceLoadingHooks does, then every NEON generating plant is checked:
  - exactly one load class group (Base Load / Intermediate / Peak)
  - MWh Rating (0x09A44AC9) equal to the power produced (0x27812852)
  - KVA Rating (0xE652E51F) = 2.5 x MWh Rating
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dbpf

FUEL = {0x1946409F: 'Coal', 0xD6B169D9: 'Oil', 0x36CA5093: 'Biomass', 0x5512235E: 'Natural Gas', 0xA945A10D: 'Fission',
        0xB680D7E0: 'Fusion', 0x1F221780: 'Geothermal', 0x7134683C: 'Solar', 0x0CED62DC: 'Microwave', 0xF0D606AC: 'Tidal',
        0xEC9175AA: 'Waste to Energy', 0x8765D979: 'Hydro', 0xC78E0054: 'Wind', 0xB075C142: 'Generators'}
EQUIPMENT = {0x861A7248, 0xED378A8E, 0x1B823F5A, 0x215395E9, 0x7AB34F1B}
CLASSES = {0x18E64EA5: 'Base Load', 0x0BADB9AC: 'Intermediate', 0x7283DCD7: 'Peak'}
KVA_PER_MWH = 2.5
EXEMPLAR, COHORT, PATCH_GROUP, PATCH_TARGETS = 0x6534284A, 0x05342861, 0xB03697D1, 0x0062E78A

def files(args):
    for a in args:
        if os.path.isdir(a):
            for root, _, names in os.walk(a):
                for n in sorted(names):
                    if n.lower().endswith(('.dat', '.sc4lot', '.sc4desc')): yield os.path.join(root, n)
        else:
            yield a

def main(args):
    exemplars, patches = {}, []
    for path in files(args):
        try:
            entries = dbpf.entries(path)
        except Exception as e:
            print('skip %s: %s' % (path, e)); continue
        for t, g, i, b in entries:
            if t not in (EXEMPLAR, COHORT): continue
            e = dbpf.exemplar(b)
            if not e or e[0] == 'text': continue
            props = {pid: v for pid, _, v in e[1]}
            if t == COHORT and g == PATCH_GROUP and PATCH_TARGETS in props:
                patches.append((path, i, props))
            elif t == EXEMPLAR:
                exemplars[(g, i)] = (path, props)
    for path, inst, props in patches:          # later files win, as in game
        targets = props[PATCH_TARGETS]
        for k in range(0, len(targets) - 1, 2):
            key = (targets[k], targets[k + 1])
            if key in exemplars:
                merged = dict(exemplars[key][1])
                merged.update({p: v for p, v in props.items() if p not in (PATCH_TARGETS, 0x20)})
                exemplars[key] = (exemplars[key][0] + ' + patch ' + os.path.basename(path), merged)
            else:
                print('patch %s 0x%08X: target 0x%08X 0x%08X not found in the scanned files' % (os.path.basename(path), inst, *key))
    plants = issues = 0
    for (g, i), (path, p) in sorted(exemplars.items()):
        groups = p.get(0xAA1DD396, [])
        if not any(x in FUEL for x in groups) or any(x in EQUIPMENT for x in groups): continue
        plants += 1
        name = p.get(0x20, ['?'])[0]
        power = p.get(0x27812852, [None])[0]; mwh = p.get(0x09A44AC9, [None])[0]; kva = p.get(0xE652E51F, [None])[0]
        problems = []
        cls = [CLASSES[x] for x in groups if x in CLASSES]
        if len(cls) != 1: problems.append('load class: %s' % (cls or 'missing'))
        if mwh is None: problems.append('no MWh Rating (DLL will use %s)' % power)
        elif power is not None and mwh != power: problems.append('MWh %s != power produced %s' % (mwh, power))
        ref = mwh if mwh is not None else power
        if kva is None: problems.append('no KVA Rating (DLL will use %s)' % (None if ref is None else round(KVA_PER_MWH * ref)))
        elif ref is not None and abs(kva - KVA_PER_MWH * ref) > 0.5: problems.append('kVA %s != 2.5 x %s' % (kva, ref))
        fuel = ', '.join(FUEL[x] for x in groups if x in FUEL)
        print('%s  0x%08X 0x%08X  %-40.40s %-12s %s' % ('OK ' if not problems else 'FIX', g, i, name, fuel, '; '.join(problems)))
        issues += bool(problems)
    print('\n%d NEON generating plants, %d to fix, %d exemplar patches' % (plants, issues, len(patches)))

if __name__ == '__main__':
    main(sys.argv[1:] or ['.'])
