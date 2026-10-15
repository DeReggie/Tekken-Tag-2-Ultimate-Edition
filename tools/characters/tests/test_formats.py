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
from ttt2char.convert import strips                   # noqa: E402
from ttt2char.tekken7 import tkmvst                   # noqa: E402
from ttt2char.ttt2 import archive, bone, bxml, nud, nut  # noqa: E402


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


if __name__ == '__main__':
    unittest.main()
