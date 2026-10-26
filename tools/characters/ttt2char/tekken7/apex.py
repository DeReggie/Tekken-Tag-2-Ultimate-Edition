"""Tekken 7's cloth: the APEX clothing assets of a skeletal mesh (its ClothingAssets).

A costume part Tekken 7 simulates cloth on (Claudio's coat, Master Raven's ribbons, Shaheen's headscarf) has a
section drawn skinned (disabled while the cloth runs) and a copy the cloth simulation moves; the skinned section's
`cloth_section` names the copy, whose `cloth_asset` names the clothing asset (mesh.py). Each asset is an APEX
NxParameterized binary file serialised after the mesh (u32 size, then the file):
    header (big-endian u32): magic 0x5A5B5C5D, type, version, object count, file size, dictionary offset, data
        offset, relocation offset, ...
    data: the parameter objects as the 64-bit little-endian structures APEX keeps in memory: an array is
        {u64 pointer, u32 allocated, i32 element size, i32 count, u32}; pointers are file offsets
    relocation table: u32 count, count x {u32 kind (0: a pointer to data), u32 offset of the pointer}
The physical (simulated) mesh is the first run of arrays: vertices (FVector), normals, skinning normals, constrain
coefficients {max distance, collision sphere radius, collision sphere distance}, bone indices (u16 x k a vertex),
bone weights (f32 x k), optimisation data (u8), then triangles (u32 x 3). A vertex's max distance is how far the
simulation lets it move from where its skin weights put it: 0 = pinned to the body. The asset's bones (88-byte
records, the name pointer at +72) name the skeleton bones the physical mesh's bone indices count.
Units are the mesh's: centimetres, Z up.

Written for this project from the files themselves (no third-party code).
"""
import re
import struct

import numpy as np

MAGIC = b'\x5a\x5b\x5c\x5d'
BONE_RECORD = 88
BONE_NAME_AT = 72


def files(data):
    """The APEX files serialised in a package's bytes (each preceded by its u32 size)."""
    out = []
    for m in re.finditer(re.escape(MAGIC), data):
        at = m.start()
        if at < 4:
            continue
        size, = struct.unpack_from('<I', data, at - 4)
        if at + 20 <= len(data) and size == struct.unpack_from('>I', data, at + 16)[0] and at + size <= len(data):
            out.append(data[at:at + size])
    return out


def _arrays(b):
    """[(element size, count, offset)] of the file's arrays, in data order, and its string pointers' targets."""
    relocations, = struct.unpack_from('>I', b, 28)
    n, = struct.unpack_from('<I', b, relocations)
    arrays = []
    for i in range(n):
        kind, at = struct.unpack_from('<II', b, relocations + 4 + 8 * i)
        if kind != 0 or at + 24 > len(b):
            continue
        target, = struct.unpack_from('<Q', b, at)
        allocated, size, count = struct.unpack_from('<Iii', b, at + 8)
        if allocated in (0, 1) and 0 < size <= 4096 and 0 <= count and target + size * count <= len(b):
            arrays.append((at, size, count, target))
    arrays.sort()
    return [(size, count, target) for _, size, count, target in arrays]


def _cstr(b, at):
    return b[at:b.index(b'\0', at)].decode('latin-1')


class Asset:
    """A clothing asset's physical mesh: vertices (n, 3) cm, max_distance (n,), triangles (m, 3), bone_names,
    bones (n, k) indices into bone_names, weights (n, k)."""

    def __init__(self, b):
        arrays = _arrays(b)
        self.bone_names = []
        for size, count, at in arrays:
            if size == BONE_RECORD:
                self.bone_names = [_cstr(b, struct.unpack_from('<Q', b, at + BONE_RECORD * i + BONE_NAME_AT)[0])
                                   for i in range(count)]
                break
        for i in range(len(arrays) - 5):
            (s0, n, a0), (s1, n1, _), (s2, _, _), (s3, n3, a3), (s4, n4, a4), (s5, n5, a5) = arrays[i:i + 6]
            if (s0, s1, s2, s3, s4, s5) == (12, 12, 12, 12, 2, 4) and n > 0 and n1 == n3 == n and n4 == n5 \
                    and n4 % n == 0:
                break
        else:
            raise ValueError('no physical mesh in the clothing asset')
        k = n4 // n
        self.vertices = np.frombuffer(b, '<f4', 3 * n, a0).reshape(n, 3).astype(np.float64)
        self.max_distance = np.frombuffer(b, '<f4', 3 * n, a3).reshape(n, 3)[:, 0].astype(np.float64)
        self.bones = np.frombuffer(b, '<u2', n * k, a4).reshape(n, k).astype(np.int64)
        self.weights = np.frombuffer(b, '<f4', n * k, a5).reshape(n, k).astype(np.float64)
        self.triangles = np.zeros((0, 3), np.int64)
        for size, count, at in arrays[i + 6:]:
            if size == 4 and count and count % 3 == 0:
                t = np.frombuffer(b, '<u4', count, at).astype(np.int64)
                if t.max() < n:
                    self.triangles = t.reshape(-1, 3)
                    break


def assets(data):
    """The clothing assets of a skeletal mesh package's bytes, in ClothingAssets order."""
    return [Asset(b) for b in files(data)]
