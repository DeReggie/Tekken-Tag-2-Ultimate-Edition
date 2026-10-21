"""The title entries the added fighters share (`<characters folder>/shared/keys/`), made for every installed pack.

Each added fighter changes some of the title's own entries: the 2D layouts (its labels beside Paul's, its select
grid cell), the big portraits' container, the fights' HUD pictures, the costume palettes and colour grid (its
player 2 colours) and the select screen's announcer bank (its name call). Packs made one by one would each carry a
copy and the last would win, so these are made here for all installed packs together, each fighter in its place
(pack.place): after an import, from the player's own files again (the pictures and name calls), and from each
pack's `colours.json` (its player 2 colours).
"""
import json
import os
import shutil

from . import pack
from .convert import art, colours, voice
from .ttt2.archive import key_of


def fighters_of(folder, definitions):
    """[(slot, definition, pack folder)] of the installed packs whose fighter the importer knows, by place."""
    places = pack.places_of(pack.installed(folder))
    out = []
    for p in pack.installed(folder):
        d = definitions.get(p['code'])
        if d is not None and p['code'] in places:
            out.append((places[p['code']], d, p['path']))
    return sorted(out, key=lambda f: f[0])


def palettes(archives, fighters):
    """The colour grid and both palettes with every fighter's player 2 colours: {file name: bytes}, or {}."""
    texts = [archives.read(k).decode('utf-8') for k in (colours.KEY_1P, colours.KEY_2P)]
    grid = colours.Palette(archives.read(colours.KEY_GRID), texts)
    placed = False
    for slot, d, folder in fighters:
        path = os.path.join(folder, 'colours.json')
        if not os.path.isfile(path):
            continue
        with open(path) as f:
            mine = {int(nn): v for nn, v in json.load(f).items()}
        entries = [{}, {}]
        for nn, (rgb1, rgb2) in sorted(mine.items()):
            entries[0][nn] = grid.place(rgb1)
            entries[1][nn] = grid.place(rgb2)
        for which in (0, 1):
            texts[which] = colours.palette_xml(texts[which], pack.place(slot)['id'], entries[which])
        placed = True
    if not placed:
        return {}
    return {'keys/%08x.bin' % colours.KEY_GRID: grid.grid_bytes(),
            'keys/%08x.bin' % colours.KEY_1P: texts[0].encode('utf-8'),
            'keys/%08x.bin' % colours.KEY_2P: texts[1].encode('utf-8')}


def name_calls(paks, archives, fighters, log=None):
    """The select screen's announcer bank with every fighter's name call: {file name: bytes}, or {}."""
    bank = archives.raw(key_of(voice.SELECT_BANK))
    changed = False
    for slot, d, folder in fighters:
        clips = voice.Clips(paks, d.TEKKEN7_CODE, d.VOICE_PREFIX)
        made = voice.name_call(clips, bank, d.DONOR, d.CODE)
        if made is not None:
            bank, changed = made, True
        elif log:
            log('no name call of %s on the select screen' % d.NAME)
    return {'keys/%08x.bin' % key_of(voice.SELECT_BANK): bank} if changed else {}


def build(paks, archives, rpx, folder, definitions, log=None):
    """Writes <folder>/shared/ for the installed packs; definitions: {code: definition}. -> the fighters it has."""
    fighters = fighters_of(folder, definitions)
    files = {}
    if fighters:
        files.update(art.shared_files(paks, archives, rpx, [(slot, d) for slot, d, _ in fighters], log=log))
        files.update(palettes(archives, fighters))
        files.update(name_calls(paks, archives, fighters, log=log))
    target = os.path.join(folder, pack.SHARED)
    part = target + '.part'
    shutil.rmtree(part, ignore_errors=True)
    for name, data in files.items():
        path = os.path.join(part, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            f.write(data)
    shutil.rmtree(target, ignore_errors=True)
    if files:
        os.replace(part, target)
    return fighters
