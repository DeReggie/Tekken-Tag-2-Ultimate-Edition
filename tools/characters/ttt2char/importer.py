"""The importer's steps: check the inputs, convert, write the pack (import_character.py is the command line)."""
import collections
import glob
import importlib
import os
import struct
import subprocess
import time

from . import InputError, pack
from .convert import idmaps, itemdb, model, moveset
from .tekken7 import tkmvst
from .tekken7.pak import Paks
from .ttt2 import motbin
from .ttt2.archive import Archives, key_of

CHARACTERS = ('kazumi',)
HEIHACHI = 8          # Tekken 7's roster id of Heihachi Mishima, the fighter both games share (for the id maps)
REPOSITORY = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))

TKMOVESETS_HELP = (
    'Save the movesets with TKMovesets2 (github.com/Kiloutre/TKMovesets) while Tekken 7 runs: Practice mode with '
    '%s as player 1 and Heihachi as player 2, then "Extract (all)" (any compression). The two .tkmvst files it '
    'writes to its extracted_chars folder are what --movesets needs.')


def definition(name):
    if name not in CHARACTERS:
        raise InputError('no fighter "%s" to import; the importer knows: %s' % (name, ', '.join(CHARACTERS)))
    return importlib.import_module('.characters.' + name, __package__)


def tekken7_paks(folder):
    """The Paks of the player's Tekken 7 PC installation (the folder holding TekkenGame/)."""
    paks = os.path.join(folder or '', 'TekkenGame', 'Content', 'Paks')
    if not folder or not glob.glob(os.path.join(paks, '*.pak')):
        raise InputError('--tekken7 must be your own Tekken 7 PC installation, the folder holding TekkenGame/ '
                         '(Steam: Library > Tekken 7 > Manage > Browse local files); found no pak files in %s'
                         % paks)
    return paks


def ttt2_folder(folder):
    """The installed Tekken Tag Tournament 2 folder (code/, content/, meta/)."""
    if folder and os.path.isfile(folder):
        raise InputError('--game must be a folder, not %s: install the game first (ttt2 --install extracts it '
                         'to a folder you choose) and give that folder' % os.path.basename(folder))
    if not folder or not os.path.isfile(os.path.join(folder, 'content', 'hdd', 'data000.ofs')):
        raise InputError('--game must be your installed Tekken Tag Tournament 2 folder (the one holding content/hdd); '
                         'ttt2 --install makes one')
    return folder


def find_movesets(folder, d):
    """{Tekken 7 roster id: path} of the fighter's and Heihachi's .tkmvst files in `folder`."""
    if not folder or not os.path.isdir(folder):
        raise InputError('--movesets must be the folder with the .tkmvst files. ' + TKMOVESETS_HELP % d.NAME)
    found = {}
    for path in sorted(glob.glob(os.path.join(folder, '*.tkmvst'))):
        with open(path, 'rb') as f:
            head = f.read(0xF0)
        if len(head) < 0xF0 or head[:4] != b'TKM2' or not head[0x90:0xB0].startswith(b'Tekken 7'):
            continue
        found.setdefault(struct.unpack_from('<I', head, 0x80)[0], path)
    missing = [who for who, i in ((d.NAME, d.TEKKEN7_ID), ('Heihachi', HEIHACHI)) if i not in found]
    if missing:
        raise InputError('%s has no Tekken 7 moveset of %s. ' % (folder, ' and '.join(missing))
                         + TKMOVESETS_HELP % d.NAME)
    return found[d.TEKKEN7_ID], found[HEIHACHI]


def output_folder(folder):
    """Where packs go; never a folder of the repository that git would commit."""
    folder = os.path.abspath(os.path.expanduser(folder or pack.default_folder()))
    real = os.path.realpath(folder)       # through symbolic links, which could lead into the repository
    if os.path.commonpath([real, REPOSITORY]) == REPOSITORY and not git_ignores(real):
        raise InputError('the pack would go into the repository (%s): packs hold Namco\'s assets and must stay out '
                         'of it; leave out --out (the default is %s)' % (folder, pack.default_folder()))
    return folder


def git_ignores(folder):
    """Whether git ignores `folder` itself (as it does local/) in the repository (False when git cannot tell): a
    name no ignore pattern covers, in that folder."""
    try:
        probe = os.path.join(folder, 'ttt2-pack-probe')
        return subprocess.run(['git', '-C', REPOSITORY, 'check-ignore', '-q', probe],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    except OSError:
        return False


def run(name, tekken7, movesets, game, out=None, log=print):
    """Imports fighter `name`; returns the pack's folder."""
    d = definition(name)
    paks_dir = tekken7_paks(tekken7)
    own, heihachi = find_movesets(movesets, d)
    game = ttt2_folder(game)
    out = output_folder(out)
    start = time.time()

    def step(text):
        log('%5.1f s  %s' % (time.time() - start, text))

    step('reading Tekken 7 (%s) and Tekken Tag Tournament 2 (%s)' % (tekken7, game))
    try:
        paks = Paks(paks_dir)
    except (OSError, ValueError, struct.error) as error:
        raise InputError('cannot read the pak files in %s (%s): let Steam verify Tekken 7\'s files' % (paks_dir, error))
    try:
        archives = Archives(game)
    except (OSError, ValueError, struct.error) as error:
        raise InputError('cannot read the archives in %s (%s): install the game again with ttt2 --install'
                         % (game, error))
    if not archives.has(key_of(d.DONOR + '.xml')):
        raise InputError('%s has no %s files: is it the Wii U game\'s folder?' % (game, d.DONOR))

    step('model: %s' % d.NAME)
    nud, nut, bon = model.convert(paks, archives, d, log=lambda s: log('         ' + s.strip()))
    xml = itemdb.body_only(archives.read_name(d.DONOR + '.xml'))

    step('moveset: the id maps from Heihachi in both games')
    k = tkmvst.read(own)
    h7 = tkmvst.read(heihachi)
    evidence = collections.defaultdict(idmaps.Evidence)
    for who, row in d.ALIGN:
        idmaps.align(k if who == 'self' else h7, motbin.read(archives.entry('data006', row)), evidence)
    req, prop = idmaps.build_maps(evidence)
    maps = (req, prop, idmaps.reaction_remap(evidence), idmaps.hitbox_remap(evidence))
    usage = idmaps.ttt2_usage([motbin.read(archives.entry('data006', row)) for row in range(58)])

    step('moveset: converting')
    c = moveset.Converter(k, h7, motbin.read(archives.entry('data006', d.DONOR_ROW)),
                          archives.entry('data005', d.DONOR_ROW), motbin.read(archives.entry('data006', 13)),
                          archives.entry('data004', 0), maps, usage, d.ROW, d)
    c.run()
    moves, motions = c.write()
    for line in c.summary():
        log('         ' + line)

    target = pack.write(out, d, {'.xml': xml, '.nud': nud, '.nut': nut, '.bon': bon,
                                 '.moveset': moves, '.motion': motions})
    step('wrote %s' % target)
    return target
