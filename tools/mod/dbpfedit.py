"""Minimal DBPF 1.0 reader/writer for SimCity 4 .dat files.

Unchanged entries are copied byte for byte (compressed ones stay compressed and keep their DIR record).
Changed or new entries are written uncompressed."""
import struct

DIR_TYPE = 0xE86B1EEF


class Entry:
    def __init__(self, t, g, i, raw, compressed):
        self.t, self.g, self.i = t, g, i
        self.raw = raw              # bytes as stored in the file
        self.compressed = compressed
        self._data = None
        self.changed = False

    @property
    def key(self):
        return (self.t, self.g, self.i)

    @property
    def data(self):
        if self._data is None:
            self._data = qfs_decompress(self.raw) if self.compressed else self.raw
        return self._data

    @data.setter
    def data(self, value):
        self._data = bytes(value)
        self.raw = self._data
        self.compressed = False
        self.changed = True


def qfs_decompress(d):
    i = 4
    assert d[i] == 0x10 and d[i + 1] == 0xFB, 'not QFS'
    i += 5
    out = bytearray()
    while i < len(d):
        c = d[i]
        if c < 0x80:
            b1 = d[i + 1]; pl = c & 3; cl = ((c & 0x1C) >> 2) + 3; off = ((c & 0x60) << 3) + b1 + 1; i += 2
        elif c < 0xC0:
            b1, b2 = d[i + 1], d[i + 2]; pl = b1 >> 6; cl = (c & 0x3F) + 4; off = ((b1 & 0x3F) << 8) + b2 + 1; i += 3
        elif c < 0xE0:
            b1, b2, b3 = d[i + 1], d[i + 2], d[i + 3]; pl = c & 3; cl = ((c & 0x0C) << 6) + b3 + 5
            off = ((c & 0x10) << 12) + (b1 << 8) + b2 + 1; i += 4
        elif c < 0xFC:
            pl = ((c & 0x1F) << 2) + 4; cl = 0; off = 0; i += 1
        else:
            pl = c & 3; cl = 0; off = 0; i += 1
        out += d[i:i + pl]; i += pl
        for _ in range(cl):
            out.append(out[-off])
        if c >= 0xFC:
            break
    return bytes(out)


class Package:
    def __init__(self, path):
        self.path = path
        d = open(path, 'rb').read()
        assert d[:4] == b'DBPF' and struct.unpack_from('<II', d, 4) == (1, 0), 'only DBPF 1.0'
        self.header = bytearray(d[:96])
        count, off, size = struct.unpack_from('<III', d, 36)
        index_version = struct.unpack_from('<I', d, 32)[0]
        assert index_version == 7, 'index version %d' % index_version
        raw = []
        for k in range(count):
            t, g, i, o, s = struct.unpack_from('<IIIII', d, off + 20 * k)
            raw.append((t, g, i, d[o:o + s]))
        compressed = set()
        for t, g, i, b in raw:
            if t == DIR_TYPE:
                for j in range(0, len(b) - 15, 16):
                    compressed.add(struct.unpack_from('<III', b, j))
        self.slots = []                                   # original index order, 'DIR' marks the directory
        for t, g, i, b in raw:
            self.slots.append('DIR' if t == DIR_TYPE else Entry(t, g, i, b, (t, g, i) in compressed))
        self.entries = [x for x in self.slots if x != 'DIR']

    def find(self, t, g=None, i=None):
        return [e for e in self.entries if e.t == t and (g is None or e.g == g) and (i is None or e.i == i)]

    def get(self, t, g, i):
        r = self.find(t, g, i)
        return r[0] if r else None

    def add(self, t, g, i, data):
        assert self.get(t, g, i) is None, 'duplicate %08X %08X %08X' % (t, g, i)
        e = Entry(t, g, i, bytes(data), False)
        e.changed = True
        self.entries.append(e)
        self.slots.append(e)
        return e

    def remove(self, entry):
        self.entries = [e for e in self.entries if e is not entry]
        self.slots = [e for e in self.slots if e is not entry]

    def duplicates(self):
        seen, dup = set(), []
        for e in self.entries:
            if e.key in seen: dup.append(e.key)
            seen.add(e.key)
        return dup

    @property
    def changed(self):
        return any(e.changed for e in self.entries)

    def save(self, path):
        """Writes entries in their original order (the DIR record where it was), new entries at the end."""
        body = bytearray(self.header)
        index = []
        dir_records = []
        for e in self.entries:
            if e.compressed:
                usize = struct.unpack_from('>I', b'\0' + e.raw[6:9])[0]
                dir_records.append(struct.pack('<IIII', e.t, e.g, e.i, usize))
        slots = list(self.slots)
        if dir_records and 'DIR' not in slots:
            slots.insert(0, 'DIR')
        for x in slots:
            if x == 'DIR':
                if dir_records:
                    d = b''.join(dir_records)
                    index.append((DIR_TYPE, DIR_TYPE, 0x286B1F03, len(body), len(d)))
                    body.extend(d)
            else:
                index.append((x.t, x.g, x.i, len(body), len(x.raw)))
                body.extend(x.raw)
        index_off = len(body)
        for rec in index:
            body.extend(struct.pack('<IIIII', *rec))
        struct.pack_into('<III', body, 36, len(index), index_off, 20 * len(index))
        open(path, 'wb').write(body)


# ------------------------------------------------------------------ exemplars and cohorts (binary)
VT = {0x01: 'B', 0x02: 'H', 0x03: 'I', 0x07: 'i', 0x08: 'q', 0x09: 'f', 0x0B: '?', 0x0C: 's'}


class Property:
    def __init__(self, pid, vtype, values, multi):
        self.id, self.vtype, self.values, self.multi = pid, vtype, list(values), multi


class Exemplar:
    def __init__(self, data):
        self.magic = data[:8]
        assert self.magic[4:] == b'1###', 'text exemplars are not supported'
        self.parent = struct.unpack_from('<III', data, 8)
        n = struct.unpack_from('<I', data, 20)[0]
        i = 24
        self.props = []
        for _ in range(n):
            pid, vt, kt = struct.unpack_from('<IHH', data, i); i += 8
            vt >>= 8
            fmt = VT[vt]
            if kt == 0:
                i += 1
                sz = struct.calcsize('<' + fmt)
                vals = [struct.unpack_from('<' + fmt, data, i)[0]]; i += sz
                self.props.append(Property(pid, vt, vals, False))
            else:
                i += 1
                cnt = struct.unpack_from('<I', data, i)[0]; i += 4
                if fmt == 's':
                    vals = [data[i:i + cnt].decode('latin-1')]; i += cnt
                else:
                    sz = struct.calcsize('<' + fmt)
                    vals = list(struct.unpack_from('<%d%s' % (cnt, fmt), data, i)); i += cnt * sz
                self.props.append(Property(pid, vt, vals, True))

    def get(self, pid):
        for p in self.props:
            if p.id == pid:
                return p
        return None

    def values(self, pid, default=None):
        p = self.get(pid)
        return p.values if p else default

    def set(self, pid, vtype, values, multi=None):
        p = self.get(pid)
        if multi is None:
            multi = len(values) != 1
        if p:
            p.vtype, p.values, p.multi = vtype, list(values), multi
        else:
            self.props.append(Property(pid, vtype, values, multi))
            self.props.sort(key=lambda x: x.id)

    def remove(self, pid):
        self.props = [p for p in self.props if p.id != pid]

    def to_bytes(self):
        out = bytearray(self.magic)
        out += struct.pack('<III', *self.parent)
        out += struct.pack('<I', len(self.props))
        for p in self.props:
            fmt = VT[p.vtype]
            out += struct.pack('<IHH', p.id, p.vtype << 8, 0x80 if p.multi else 0)
            out += b'\0'
            if not p.multi:
                out += struct.pack('<' + fmt, p.values[0])
            elif fmt == 's':
                s = p.values[0].encode('latin-1')
                out += struct.pack('<I', len(s)) + s
            else:
                out += struct.pack('<I', len(p.values)) + struct.pack('<%d%s' % (len(p.values), fmt), *p.values)
        return bytes(out)


# ------------------------------------------------------------------ LTEXT
def ltext_decode(data):
    n, mark = struct.unpack_from('<HH', data, 0)
    if mark == 0x1000 and len(data) == 4 + 2 * n:
        return data[4:].decode('utf-16le'), True
    return data.decode('latin-1'), False


def ltext_encode(text):
    return struct.pack('<HH', len(text), 0x1000) + text.encode('utf-16le')
