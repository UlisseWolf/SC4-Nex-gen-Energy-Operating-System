"""Corrects the 2x2 Maxis Power Substation lot (88630077) for NEON and writes it to extra/.
usage: python fix_substation_lot.py <source .SC4Lot> <output .SC4Lot>"""
import re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dbpfedit import Package, ltext_decode, ltext_encode

src, dst = sys.argv[1:3]
p = Package(src)
changes = []

def edit_text(e, pid, new_value_text, label):
    t = e.data.decode('latin-1')
    pat = re.compile(r'(0x%08x:\{"[^"]*"\}=[A-Za-z0-9]+:\d+:\{)([^}]*)(\})' % pid, re.I)
    m = pat.search(t)
    assert m, label
    old = m.group(2)
    t = t[:m.start(2)] + new_value_text + t[m.end(2):]
    e.data = t.encode('latin-1')
    changes.append('%s: %s -> %s' % (label, old, new_value_text))

building = next(e for e in p.entries if e.t == 0x6534284A and e.g == 0x55FDAF8F and e.i == 0x88630077)
lot = next(e for e in p.entries if e.t == 0x6534284A and e.g == 0xA8FBD372 and e.i == 0x88630077)
assert building.data[:8] == b'EQZT1###' and lot.data[:8] == b'EQZT1###'

# 1. 10 MVA transmission station (the Reader template computed int(Volume/2) = 16 from the small pole model)
edit_text(building, 0xE652E51F, '0x00002710', 'building KVA Rating')
# 2. NEON transmission station query
edit_text(building, 0x2A499F85, '0xbb353120', 'building Query exemplar GUID')
# 3. building (the pole) back where Takingyouthere placed it, so the wire props reach it
edit_text(lot, 0x88EDC900, '0x00000000,0x00000000,0x00000001,0x0012ff2c,0x00000000,0x000bbbbb,0x0011ebb4,0x000aa7a6,0x001412a4,0x000ccfd1,0x00000000,0x00000000,0x88630077',
          'lot building object (position / rotation of the pole)')
# 4. conditional building: available only through the NEON reward (transmission_station_hex_id.MVA_10_1)
t = building.data.decode('latin-1')
assert '0xea3209f8' not in t.lower()
nl = '\r\n' if '\r\n' in t else '\n'
line = '0xea3209f8:{"Conditional Building"}=Bool:0:{True}'
m = re.search(r'^0xea54d283:', t, re.M | re.I)          # keep the properties sorted by ID
t = t[:m.start()] + line + nl + t[m.start():]
count = int(re.search(r'PropCount=0x([0-9A-Fa-f]+)', t).group(1), 16)
t = re.sub(r'PropCount=0x[0-9A-Fa-f]+', 'PropCount=0x%08X' % (count + 1), t, count=1)
building.data = t.encode('latin-1')
changes.append('building: Conditional Building (0xEA3209F8) = True, PropCount %d -> %d' % (count, count + 1))
# 5. description
desc = next(e for e in p.entries if e.t == 0x2026960B and e.g == 0x55FDAF8F and e.i == 0x88630077)
old = ltext_decode(desc.data)[0]
new = ('10 MVA transmission substation. Steps the power of large power plants up to the transmission grid '
       'and feeds the distribution substations (NEON).')
desc.data = ltext_encode(new)
changes.append('description LTEXT: "%s" -> "%s"' % (old, new))

# 6. menu icon: the NEON icon of the Maxis Power Substation (the lot had an empty grey icon)
icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'extra', 'icon_maxis_power_substation.png')
icon = next(e for e in p.entries if e.t == 0x856DDBAC and e.g == 0x6A386D26 and e.i == 0x88630077)
icon.data = open(icon_path, 'rb').read()
changes.append('menu icon 856DDBAC/6A386D26/88630077 replaced with the NEON Maxis Power Substation icon (176x44)')

p.save(dst)
print('\n'.join(changes))
