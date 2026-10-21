"""Character packs: what the port loads to add a fighter (runtime/src/title/roster.cpp).

A pack is a folder `<code>/` in the characters folder ($TTT2_CHARACTERS, else ~/.local/share/ttt2/characters):
    character.ini              code = <three letters>, donor = <a TTT2 fighter's code>, sex = female | male,
                               slot = its number k (place(k): select id 64 + k, its motion row and grid cell),
                               chr_tones = its voice bank's shout tones (the win quotes' come after)
    <code>.xml                 item database (BXML)
    <code>.nud .nut .bon       body model, textures, skeleton
    <code>.mop                 spring entries of its extra bones (Kazumi's tiger)
    <code>.moveset .motion     moveset (motbin) and motion pack
    <code>.mvl                 the practice command list (MVLT)
    se_Chr_<code>.nus3bank     its voice: shouts, damage voices, the announcer's call, then its win quotes (the first
                               chr_tones tones are the shouts'); intro lines (rm_Dst_); the long win quote one win
    rm_Dst_<code>.nus3bank     pose streams (rm_Dwi_)
    rm_Dwi_<code>.nus3bank
    art/                       its pictures for the loading and VS screens and the costume chooser (the port shows
                               its art when the pack has this folder)
    colours.json               its player 2 colours (palette number: 1P and 2P colour), for shared/
The packs share `shared/keys/` (made for all of them together, shared.py): changed copies of the title's own entries
(2D layouts with every added fighter's pictures, the big portraits' container, the costume palettes and colour grid,
the select screen's name calls; `<key>.bin`) and texture pages to add to its texture containers (`<key>.add`).
Files a pack leaves out (<code>.mop, .havok.xml: spring bones and cloth collision; <code>.mvl: the practice
command list; the sound banks) are the donor's. A pack holds the other game's assets: it is for the player's own use only.
"""
import os

FILES = ('.xml', '.nud', '.nut', '.bon', '.moveset', '.motion')
SHARED = 'shared'               # the packs' shared title entries
# Added fighter k's place as the port gives it (roster.cpp): select id 64 + k, a motion row (what the moveset's
# fighter fields hold: the rows no fighter has first, then 69 on) and a select grid cell (roster.cpp kCells): the free
# ends of the top row, then columns beyond the grid's ends (-1 and 23, then -2 and 24). A cell is
# (column, grid row, anchor, columns from it): its picture goes where the grid panel of fighter `anchor` (in grid
# row 1, or the cell's own row) is, that many columns over, in the cell's row (row 0: at the top row's height).
FIRST_ID = 64
DIRECT_ROWS = (58, 64, 61, 62, 65)
FIRST_VIRTUAL_ROW = 69
CELLS = ((19, 0, 'edd', 0), (2, 0, 'bru', 0), (20, 0, 'lee', 0), (1, 0, 'rav', 0), (21, 0, 'lei', 0), (0, 0, 'rog', 0),
         (22, 0, 'kum', 0),
         (23, 0, 'kum', 1), (-1, 0, 'rog', -1), (23, 1, 'kum', 1), (-1, 1, 'rog', -1), (23, 2, 'pan', 1),
         (-1, 2, 'mok', -1),
         (24, 1, 'kum', 2), (-2, 1, 'rog', -2), (24, 2, 'pan', 2), (-2, 2, 'mok', -2), (24, 0, 'kum', 2),
         (-2, 0, 'rog', -2))
MAX_FIGHTERS = 128


def place(k):
    """dict(id, row, column, grid_row, anchor, columns) of added fighter k (the cell's fields None when the grid is
    full)."""
    row = DIRECT_ROWS[k] if k < len(DIRECT_ROWS) else FIRST_VIRTUAL_ROW + k - len(DIRECT_ROWS)
    column, grid_row, anchor, columns = CELLS[k] if k < len(CELLS) else (None, None, None, None)
    return dict(id=FIRST_ID + k, row=row, column=column, grid_row=grid_row, anchor=anchor, columns=columns)


def default_folder():
    if os.environ.get('TTT2_CHARACTERS'):
        return os.environ['TTT2_CHARACTERS']
    data = os.environ.get('XDG_DATA_HOME') or os.path.join(os.path.expanduser('~'), '.local', 'share')
    return os.path.join(data, 'ttt2', 'characters')


def character_ini(d, slot, chr_tones=0, voice_extra=(), weapons=()):
    """voice_extra: the se_Chr tones of the shouts past the donor's (the port appends them to the voice list);
    weapons: weapons.of_skeleton's [(k, parent bone, [point numbers])] (the port poses them)."""
    return ('# %s, from Tekken 7 (made on this machine from the player\'s own copy)\n'
            'code = %s\ndonor = %s\nsex = %s\nslot = %d\nchr_tones = %d\n'
            % (d.NAME.split(' (')[0], d.CODE, d.DONOR, d.SEX, slot, chr_tones)
            + ('voice_extra = %s\n' % ' '.join(map(str, voice_extra)) if voice_extra else '')
            + ('weapons = %s\n' % ' '.join('%d:%d:%s' % (k, parent, ','.join(map(str, points)))
                                          for k, parent, points in weapons) if weapons else ''))


def read_ini(path):
    """{key: value} of a character.ini."""
    out = {}
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.split('#', 1)[0]
            if '=' in line:
                k, v = line.split('=', 1)
                out[k.strip()] = v.strip()
    return out


def installed(folder):
    """The packs in the characters folder: [{'path', 'code', 'donor', 'slot' (None if it names none)}], by folder
    name."""
    out = []
    if not os.path.isdir(folder):
        return out
    for name in sorted(os.listdir(folder)):
        ini = os.path.join(folder, name, 'character.ini')
        if not os.path.isfile(ini):
            continue
        v = read_ini(ini)
        slot = v.get('slot', '')
        out.append(dict(path=os.path.join(folder, name), code=v.get('code', ''), donor=v.get('donor', ''),
                        slot=int(slot) if slot.isdigit() else None))
    return out


def places_of(packs):
    """{pack code: slot} as the port gives them: the slot a pack names (the first pack naming it), else the first
    free one; packs left over get none."""
    taken, out = {}, {}
    for p in packs:
        if p['slot'] is not None and p['slot'] < MAX_FIGHTERS and p['slot'] not in taken:
            taken[p['slot']] = p['code']
    for p in packs:
        if p['code'] in taken.values():
            continue
        free = [k for k in range(MAX_FIGHTERS) if k not in taken]
        if free:
            taken[free[0]] = p['code']
    for k, code in taken.items():
        out[code] = k
    return out


def choose_slot(folder, code):
    """The place for a fighter being (re)imported: its pack's, else the first one no other pack has; None when all
    are taken."""
    packs = installed(folder)
    places = places_of(packs)
    if code in places:
        return places[code]
    used = set(places.values())
    free = [k for k in range(MAX_FIGHTERS) if k not in used]
    return free[0] if free else None


def write(folder, d, files, slot, chr_tones=0, voice_extra=(), weapons=()):
    """Writes the pack <folder>/<code>/ from files {suffix or file name: bytes} (a suffix starts with '.': the file
    is <code><suffix>); returns its path. Files of an earlier pack with the same names are replaced, and its `keys/`
    (made for a pack alone, before packs shared theirs) goes; nothing else in the folder is touched."""
    target = os.path.join(folder, d.CODE)
    os.makedirs(target, exist_ok=True)
    old_keys = os.path.join(target, 'keys')
    if os.path.isdir(old_keys):
        for name in os.listdir(old_keys):
            if len(name) == 12 and name[8:] in ('.bin', '.add'):
                os.remove(os.path.join(old_keys, name))
        if not os.listdir(old_keys):
            os.rmdir(old_keys)
    for name in files:
        if '/' in name:
            os.makedirs(os.path.join(target, os.path.dirname(name)), exist_ok=True)
    out = {'character.ini': character_ini(d, slot, chr_tones, voice_extra, weapons).encode('utf-8')}
    out.update({(d.CODE + name if name.startswith('.') else name): data for name, data in files.items()})
    for name, data in out.items():
        sub, base = os.path.split(name)
        tmp = os.path.join(target, sub, '.' + base + '.part')
        with open(tmp, 'wb') as f:
            f.write(data)
        os.replace(tmp, os.path.join(target, name))
    return target
