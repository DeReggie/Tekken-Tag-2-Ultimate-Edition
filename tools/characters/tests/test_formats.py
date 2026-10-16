"""Unit tests of the importer's formats and helpers on made-up data (no game files needed).

    python3 -m unittest discover tools/characters/tests
"""
import lzma
import os
import struct
import sys
import unittest
import zlib

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from ttt2char import lz4                              # noqa: E402
from ttt2char.convert import art, colours, movelist, strips  # noqa: E402
from ttt2char.tekken7 import tkmvst, wwise            # noqa: E402
from ttt2char.ttt2 import archive, bone, bxml, dsp, nud, nus3bank, nut  # noqa: E402


class Archive(unittest.TestCase):
    def test_keys(self):
        # a name's key: CRC-32 with the register starting at zero; a pack member: continued over base-4 digits
        self.assertEqual(archive.key_of('abc.nud'), zlib.crc32(b'abc.nud', 0xFFFFFFFF))
        base = archive.key_of('pack')
        self.assertEqual(archive.member_key(base, 0), base)
        self.assertEqual(archive.member_key(base, 6), zlib.crc32(bytes([2, 1]), base))      # 6 = 1*4 + 2

    def test_scramble_and_pack(self):
        data = bytes(range(256)) * 3 + b'tail'
        once = archive.scramble(data, 0x1234ABCD)
        self.assertNotEqual(once, data)
        self.assertEqual(archive.scramble(once, 0x1234ABCD), data)
        stored = archive.pack(data, 0x55AA55AA)
        self.assertEqual(archive.unpack(stored, 0x55AA55AA), data)

    def test_index(self):
        def chunk(tag, payload):
            return struct.pack('>I', 8 + len(payload)) + tag + payload
        keys, sizes = [0x11111111, 0x22222222], [20, 32]
        offsets, at = [], 0
        for size in sizes:
            offsets.append(at | (size % 16))
            at += (size + 15) & ~15
        offsets.append(at)
        ofs = (chunk(b'ftyp', b'nrfo\0\1\0\1') + chunk(b'head', bytes(20)) +
               chunk(b'ofsi', b''.join(struct.pack('>II', k, 0) for k in keys)) +
               chunk(b'ofsd', b''.join(struct.pack('>I', o) for o in offsets)))
        index = archive.parse_index(ofs)
        self.assertEqual([e[0] for e in index], keys)
        self.assertEqual([e[3] for e in index], sizes)


class Lz4(unittest.TestCase):
    def test_literals_and_matches(self):
        # token 0x4F: 4 literals "abcd", then a match of 4 + 15 + 1 = 20 bytes at distance 4 (overlapping copy);
        # last sequence: 5 literals
        block = bytes([0x4F]) + b'abcd' + struct.pack('<H', 4) + bytes([1]) + bytes([0x50]) + b'vwxyz'
        self.assertEqual(lz4.decompress_block(block, 4 + 20 + 5), b'abcd' * 6 + b'vwxyz')


class Textures(unittest.TestCase):
    def test_bc1_bc3(self):
        y, x = np.mgrid[0:16, 0:16]
        img = np.stack([64 + x * 4, 64 + y * 4, np.full_like(x, 128), 128 + (x + y) * 2], -1).astype(np.uint8)
        for fmt in (0, 2):
            t = nut.make_texture(img, 0x10408000, fmt, mips=3)
            self.assertEqual(len(t['mips']), 3)
            back = nut.read(nut.write(dict(textures=[t])))['textures'][0]
            out = nut.decode(back)[0] if isinstance(nut.decode(back), list) else nut.decode(back)
            rgb = np.asarray(out)[..., :3].astype(int)
            self.assertLess(np.abs(rgb - img[..., :3].astype(int)).mean(), 4, 'format %d' % fmt)


class Skeleton(unittest.TestCase):
    def test_round_trip(self):
        n = 3
        s = dict(scale=0.98, parent=[-1, 0, 1], t=np.arange(9, dtype=np.float32).reshape(3, 3),
                 r=np.zeros((3, 3), np.float32), opt=[7], params=[1.0] * 8, names=['root', 'a', 'b'],
                 s=np.ones((n, 3), np.float32))
        d = bone.write(s)
        back = bone.read(d)
        self.assertEqual(back['names'], s['names'])
        self.assertEqual(back['parent'], s['parent'])
        self.assertTrue(np.array_equal(back['t'], s['t']))
        self.assertEqual(bone.write(back), d)


class ItemDatabase(unittest.TestCase):
    def test_round_trip(self):
        tree = [dict(tag='InstanceInfo', attrs=[], children=[
                    dict(tag='Instance', attrs=[('label', 'x_1p'), ('index', '1')], children=[
                        dict(tag='Data', attrs=[('Name', 'one'), ('EquipType', 'kind')], children=[]),
                        dict(tag='Model', attrs=[('section', 'A')], children=[])])]),
                dict(tag='OffsetInfo', attrs=[], children=[])]
        d = bxml.write(tree)
        self.assertEqual(d[:4], b'BXML')
        self.assertEqual(bxml.write(bxml.parse(d)), d)


class Model(unittest.TestCase):
    def test_round_trip(self):
        vt, ut = 0x13, 0x12
        verts = np.zeros(3, nud.vertex_dtype(vt, ut))
        verts['pos'] = [[0, 0, 0], [1, 0, 0], [0, 1, 0]]
        verts['pw'] = 100.0
        verts['bones'] = [[1, 0, 0, 0]] * 3
        verts['w'] = [[1, 0, 0, 0]] * 3
        material = dict(flags=0x94010161, zero=0, src=0, dst=0, alpha_test=0, alpha_func=0, ref=0, cull=0x405,
                        u1=0, u2=0, zoff=0, textures=[dict(id=0x10408000, pad4=bytes(6), map=0, wrap_s=1,
                                                         wrap_t=1, min=1, mag=1, mip=1, b17=0, tail=bytes(6))],
                        props=[('NU_colorSamplerUV', [1.0, 1.0, 0.0, 0.0])])
        model = dict(version=0x0201, sphere=(0, 0, 0, 2), bone_first=0, bone_last=1, meshes=[
            dict(name='m', sphere=(0, 0, 0, 2), center=(0, 0, 0), sort_bias=0.0, zero=0, boneflag=4, singlebind=-1,
                 polys=[dict(vtype=vt, uvtype=ut, pflag=0, tail=bytes(12),
                             indices=np.array([0, 1, 2], np.uint16), verts=verts, materials=[material])])])
        d = nud.write(model)
        self.assertEqual(d[:4], b'NDP3')
        self.assertEqual(nud.write(nud.read(d)), d)


class Strips(unittest.TestCase):
    def test_stripify(self):
        rng = np.random.default_rng(1)
        grid = [(r * 6 + c, r * 6 + c + 1, (r + 1) * 6 + c) for r in range(5) for c in range(5)]
        tris = [grid[i] for i in rng.permutation(len(grid))]
        self.assertTrue(strips.check(tris, strips.stripify(tris)))


class Movesets(unittest.TestCase):
    def test_lzma_container(self):
        header = bytearray(0x100)
        header[:4] = b'TKM2'
        struct.pack_into('<I', header, 0x50, 0x100)
        payload = bytes(range(200)) * 10
        struct.pack_into('<Q', header, 0x58, len(payload))
        header[0x60] = 2
        packed = bytes(header) + lzma.compress(payload)
        out = tkmvst.decompress(packed)
        self.assertEqual(out[0x100:], payload)


class Voice(unittest.TestCase):
    def test_fnv(self):
        self.assertEqual(wwise.fnv('ABC'), wwise.fnv('abc'))          # ids hash the lower-case name
        h = 2166136261
        for c in b'abc':
            h = ((h * 16777619) & 0xFFFFFFFF) ^ c
        self.assertEqual(wwise.fnv('abc'), h)

    def test_wwise_ima(self):
        # one mono block: header {sample 0, step index 0}, codes 4 then 0 (low half first), then zeros
        block = struct.pack('<hBB', 0, 0, 0) + bytes([0x04]) + bytes(31)
        fmt = struct.pack('<HHIIHH', 2, 1, 48000, 27000, 36, 4) + struct.pack('<HHI', 6, 0, 0)
        body = b'WAVE' + b'fmt ' + struct.pack('<I', len(fmt)) + fmt + b'data' + struct.pack('<I', len(block)) + block
        rate, a = wwise.decode_wem(b'RIFF' + struct.pack('<I', len(body)) + body)
        self.assertEqual((rate, a.shape), (48000, (1, 64)))
        self.assertEqual(a[0, :2].tolist(), [7, 8])      # step 7: +7; then index 2 (step 9): +9 >> 3

    def test_dsp_round_trip(self):
        t = np.arange(14 * 200)
        x = (8000 * np.sin(t * 0.05) + 3000 * np.sin(t * 0.31)).astype(np.int16)
        rate, back = dsp.read_idsp(dsp.idsp([x, x // 2], 32000))
        self.assertEqual(rate, 32000)
        for orig, got in zip((x, x // 2), back):
            e = got.astype(float) - orig.astype(float)
            self.assertGreater(10 * np.log10((orig.astype(float) ** 2).mean() / max((e ** 2).mean(), 1e-9)), 20)

    def test_nus3bank(self):
        def tone(name, audio, link=None, at=0):
            n = name.encode() + b'\0'
            head = (bytes(4) + b'\x7f' + bytes(3)) if link else (bytes(4) + bytes([0xff, 0xff, 0x27, 0x84]) + b'\x7f' + bytes(3))
            t = bytearray(head + bytes([len(n)]) + n)
            while len(t) % 4:
                t.append(0)
            if link:
                t += b'\xff\xff\xff\xff' + struct.pack('<II', len(link), 1) + b''.join(
                    struct.pack('<fIIII', 1.0, k, 0, 0, 0) for k in link)
            else:
                t += struct.pack('<IIII', 0, 8, at, len(audio)) + bytes(16) + b'\xff\xff\xff\xff' + struct.pack(
                    '<III', 48000, 1, 10) + bytes(8)
            return bytes(t)
        tones = [tone('a_01', b'AAAA' * 4), tone('b_02', b'BB' * 8, at=16), tone('l_00', None, link=[0, 1])]
        table, body = struct.pack('<I', len(tones)), b''
        for t in tones:
            table += struct.pack('<II', 4 + 8 * len(tones) + len(body), len(t))
            body += t
        pack = b'AAAA' * 4 + b'BB' * 8
        chunks = [(b'BINF', struct.pack('<II', 0, 3) + bytes([5]) + b'test\0' + bytes(2) + struct.pack('<I', 7)),
                  (b'TONE', table + body), (b'PACK', pack)]
        toc = struct.pack('<I', len(chunks)) + b''.join(t + struct.pack('<I', len(d)) for t, d in chunks)
        rest = b'BANKTOC ' + struct.pack('<I', len(toc)) + toc + b''.join(t + struct.pack('<I', len(d)) + d
                                                                         for t, d in chunks)
        data = b'NUS3' + struct.pack('<I', len(rest)) + rest
        b = nus3bank.Bank(data)
        self.assertEqual(b.write(), data)
        self.assertEqual([b.name(i) for i in range(3)], ['a_01', 'b_02', 'l_00'])
        self.assertEqual([k for _, k in b.links(2)], [0, 1])
        b.replace(1, b'CCCCCCCC', 32000, 1, 4)
        k = b.append(b.renamed(0, 'a_09'), audio=b'DDDD')
        b2 = nus3bank.Bank(b.write())
        self.assertEqual((b2.audio[1], b2.format(1), b2.name(k), b2.audio[k]), (b'CCCCCCCC', (32000, 1, 4), 'a_09', b'DDDD'))


class CommandList(unittest.TestCase):
    def test_convert(self):
        strings = bytearray(b'\0')                      # offset 0: the empty string
        def put(s):
            strings.extend(s.encode() + b'\0')
            return len(strings) - len(s.encode()) - 1
        names = [put('jp'), put('Move'), put('reading'), put('Move')] + [put('cmd%d' % i) for i in range(12)]
        so = 0x20
        names = [so + o for o in names]
        entry = bytearray(372)
        struct.pack_into('<16I', entry, 0, *names)
        struct.pack_into('<HHHH', entry, 0x44, 0, 1, 0, 1)
        drill = bytearray(372)
        struct.pack_into('<16I', drill, 0, *names)
        struct.pack_into('<HHHH', drill, 0x44, 0xFFFF, 0, 15, 0)
        while len(strings) % 4:
            strings.append(0)
        eo = so + len(strings)
        do = eo + 2 * 372
        io = do + 24
        demo = struct.pack('<8HIHH', 0, 2000, 0, 0, 0, 0, 0, 1, 0, 0, 0)
        m = struct.pack('<4sHHIIIIII', b'MVLT', 1000, 2, 2, 1, so, eo, do, io) + bytes(strings) + bytes(entry) + \
            bytes(drill) + demo + bytes([0x20, 0x80, 3, 1])
        out = movelist.convert(m, log=lambda s: None)
        magic, ver, _, n, nd, so2, eo2, do2, io2 = struct.unpack_from('>4sHHIIIIII', out, 0)
        self.assertEqual((magic, ver, n, nd), (b'MVLT', 2, 1, 1))
        first = struct.unpack_from('>12I', out, eo2)
        self.assertEqual(out[so2 + first[1]:].split(b'\0')[0], b'Move')
        self.assertEqual(out[so2 + first[4]:].split(b'\0')[0], b'cmd1')     # en <- Tekken 7's [5]
        self.assertEqual(out[io2:io2 + 4], bytes([0x80, 0x20, 3, 1]))          # buttons, direction swapped


class Colours(unittest.TestCase):
    def test_fit_and_palette(self):
        grid = np.zeros((32, 64, 3, 3), '>f4')
        texts = ['<Colors>\n\t<Color id="0" palette="51" x="64" y="32" s="0" />\n</Colors>']
        pal = colours.Palette(grid.tobytes(), texts)
        c1 = np.full((8, 8, 3), 0.9)
        c1[:, 4:] = (0.8, 0.1, 0.1)                     # red in both
        c2 = c1.copy()
        c2[:, :4] = (0.2, 0.2, 0.25)                     # white -> dark in 2P
        f = colours.fit(c1, c2, pal)
        self.assertTrue((f['alpha'][:, :4] == 1).all() and (f['alpha'][:, 4:] == 0).all())
        (e1, q1, e2, q2), _ = f['groups']
        self.assertNotEqual(e1[:2], (64, 32))            # a cell the game uses is never taken
        g = np.frombuffer(pal.grid_bytes(), '>f4').reshape(32, 64, 3, 3)
        self.assertTrue(np.allclose(g[e2[1] - 1, e2[0] - 1, 1], q2, atol=1e-6))
        xml = colours.palette_xml(texts[0], 61, {51: e1})
        self.assertIn('<Color id="61" palette="51" x="%d" y="%d" s="9" />' % e1[:2], xml)


class Lettering(unittest.TestCase):
    @staticmethod
    def name(widths, spaces=()):
        """A made-up name picture: opaque bars as letters (3 pixels apart, wider at `spaces`), a dark shadow."""
        pic = np.zeros((20, 8 + sum(widths) + 3 * len(widths) + 8 * len(spaces) + 8, 4), np.float32)
        x = 8
        for i, w in enumerate(widths):
            if i in spaces:
                x += 8
            pic[5:15, x:x + w] = (0.8, 0.8, 0.8, 1.0)
            x += w + 3
        solid = pic[..., 3] == 1.0
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                near = np.roll(np.roll(solid, dy, 0), dx, 1) & ~solid
                pic[near] = (0.0, 0.0, 0.0, 0.5)
        return pic

    def test_letters(self):
        letters = art.Letters()
        letters.learn('AB C', self.name([4, 6, 5], spaces=(2,)))
        letters.learn('BA', self.name([6, 4]))
        self.assertEqual(sorted(letters.glyphs), ['A', 'B', 'C'])
        pic = letters.picture('CAB')
        cols = np.nonzero((pic[..., 3] > 0.95).any(0))[0]
        runs = np.split(cols, np.nonzero(np.diff(cols) > 1)[0] + 1)
        self.assertEqual([len(r) for r in runs], [5, 4, 6])              # C, A, B as learnt
        self.assertEqual([runs[i + 1][0] - runs[i][-1] - 1 for i in range(2)], [3, 3])
        self.assertTrue(0.4 < pic[10, cols[0] - 1, 3] < 0.6)            # the shadow next to a letter
        self.assertIsNone(letters.picture('Q'))


if __name__ == '__main__':
    unittest.main()
