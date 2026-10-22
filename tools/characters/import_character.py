#!/usr/bin/env python3
"""Adds a fighter from your own copy of Tekken 7 (PC) to Tekken Tag Tournament 2 (this repository's port).

Everything the fighter is made of is read from your files when you run this: your Tekken 7 installation (found
through Steam), its movesets and your installed Tekken Tag Tournament 2. The result is a character pack in
~/.local/share/ttt2/characters/<code>/, which the game loads at start-up. The pack holds Namco's assets: keep it for
yourself, never upload or share it.

    python3 tools/characters/import_character.py kazumi --game ~/Games/TekkenTag2
    python3 tools/characters/import_character.py --all --game ~/Games/TekkenTag2

A moveset Tekken 7 only has while it runs: the ones not saved yet are saved first (dump_tekken7.py: Tekken 7 runs in
the background, no window, no sound; Steam must be running), and so are the files Tekken 7 keeps encrypted (Geese's
and Noctis's), as the game reads them. Fighters whose DLC your account does not own are skipped.
Movesets saved from your own Tekken 7 with TKMovesets2 work too (--movesets); DLC fighters are imported only when your
Steam account owns them.

Needs Python 3 with numpy and Pillow.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    parser = argparse.ArgumentParser(
        description='Add a fighter from your own Tekken 7 (PC) to Tekken Tag Tournament 2.',
        epilog='The pack holds Namco\'s assets: it is for your own use; never upload or share it.')
    parser.add_argument('fighter', nargs='*', help='who to add (one or more): kazumi, chloe, eliza, claudio, akuma, '
                        'gigas, josie, katarina, master_raven, shaheen, fahkumram, leroy, lidia, kunimitsu2, negan, '
                        'geese, noctis')
    parser.add_argument('--all', action='store_true', help='every fighter above that your Tekken 7 has')
    parser.add_argument('--tekken7', metavar='FOLDER',
                        help='your Tekken 7 PC installation (the folder holding TekkenGame/; default: found through Steam)')
    parser.add_argument('--movesets', metavar='FOLDER',
                        help='the folder with the .tkmvst movesets saved from your own Tekken 7 (default: %s, filled as '
                             'needed)' % '~/.local/share/ttt2/tekken7/movesets')
    parser.add_argument('--files', metavar='FOLDER',
                        help='the folder with the files Tekken 7 keeps encrypted (Geese\'s, Noctis\'s), as the game reads '
                             'them (default: %s, filled as needed)' % '~/.local/share/ttt2/tekken7/files')
    parser.add_argument('--game', required=True, metavar='FOLDER',
                        help='your installed Tekken Tag Tournament 2 (the folder ttt2 --install made)')
    parser.add_argument('--out', metavar='FOLDER',
                        help='where character packs go (default: $TTT2_CHARACTERS, else ~/.local/share/ttt2/characters)')
    parser.add_argument('--no-shared', action='store_true',
                        help='leave what the packs share (shared/) as it is: for a fighter whose pictures, 2P colours '
                             'and name call have not changed')
    args = parser.parse_args()

    missing = []
    for module in ('numpy', 'PIL'):
        try:
            __import__(module)
        except ImportError:
            missing.append({'PIL': 'Pillow'}.get(module, module))
    if missing:
        sys.exit('import_character: needs the Python packages %s (e.g. pip install %s, or your distribution\'s '
                 'python-numpy / python-pillow)' % (', '.join(missing), ' '.join(missing)))

    sys.path.insert(0, HERE)
    from ttt2char import InputError, importer
    from ttt2char import pack
    from ttt2char.tekken7 import autodump
    from ttt2char.tekken7.pak import Paks
    fighters = list(importer.CHARACTERS) if args.all else [f.lower() for f in args.fighter]
    if not fighters:
        parser.error('name the fighters to add, or --all')
    for fighter in fighters:
        try:
            importer.definition(fighter)
        except InputError as error:
            sys.exit('import_character: %s' % error)
    try:
        tekken7 = os.path.expanduser(args.tekken7) if args.tekken7 else autodump.find_tekken7().game
    except autodump.DumpError as error:
        sys.exit('import_character: %s (or give --tekken7)' % error)
    movesets = os.path.expanduser(args.movesets or os.path.join('~', '.local', 'share', 'ttt2', 'tekken7', 'movesets'))
    files_folder = os.path.expanduser(args.files) if args.files else autodump.FILES
    # only fighters the player owns, whichever movesets are already saved (DLC fighters: as Steam tells)
    try:
        skipped = autodump.unowned([importer.definition(f).TEKKEN7_ID for f in fighters])
    except autodump.DumpError as error:
        sys.exit('import_character: %s' % error)
    for fighter in list(fighters):
        d = importer.definition(fighter)
        if d.TEKKEN7_ID in skipped:
            print('Skipped %s: %s.' % (d.NAME, skipped[d.TEKKEN7_ID]))
            fighters.remove(fighter)
    if not fighters:
        sys.exit('import_character: none of the fighters asked for is owned')
    # the movesets and encrypted files not saved yet: Tekken 7 in the background, once for all of them
    try:
        paks = Paks(importer.tekken7_paks(tekken7), saved=files_folder)
    except InputError as error:
        sys.exit('import_character: %s' % error)
    have = importer.saved_movesets(movesets)
    needed, files = {}, {}
    for fighter in fighters:
        d = importer.definition(fighter)
        if d.TEKKEN7_ID not in have:
            needed[d.TEKKEN7_ID] = (d.TEKKEN7_CODE, d.NAME)
        entries = autodump.unsaved_files(paks, d.TEKKEN7_CODE)
        if entries:
            files[d.TEKKEN7_ID] = (d.NAME, entries)
    if importer.HEIHACHI not in have:                       # (every import needs his)
        needed[importer.HEIHACHI] = ('hei', 'Heihachi')
    if needed or files:
        print('Saving %d Tekken 7 moveset(s) and %d fighter(s)\' encrypted files first (Tekken 7 runs hidden in the '
              'background for a minute or two) ...' % (len(needed), len(files)))
        try:
            _, skipped = autodump.dump(needed, movesets, files=files, paks=paks)
        except autodump.DumpError as error:
            sys.exit('import_character: %s' % error)
        who = {fid: name for fid, (_, name) in needed.items()}
        who.update((fid, name) for fid, (name, _) in files.items())
        for fid, why in skipped.items():
            print('Skipped %s: %s.' % (who[fid], why))
        have = importer.saved_movesets(movesets)
        fighters = [f for f in fighters if importer.definition(f).TEKKEN7_ID in have and
                    not autodump.unsaved_files(paks, importer.definition(f).TEKKEN7_CODE)]
        if importer.HEIHACHI not in have:
            sys.exit('import_character: Heihachi\'s moveset could not be saved')
        if not fighters:
            sys.exit('import_character: none of the fighters asked for could be saved from Tekken 7')
    for n, fighter in enumerate(fighters):
        try:
            # what the packs share is made once, after the last fighter
            target = importer.run(fighter, tekken7, movesets, os.path.expanduser(args.game),
                                  args.out and os.path.expanduser(args.out), make_shared=not args.no_shared and n + 1 == len(fighters),
                                  files=files_folder)
        except InputError as error:
            sys.exit('import_character: %s' % error)
        slot = int(pack.read_ini(os.path.join(target, 'character.ini')).get('slot', '0'))
        cell = pack.place(slot)
        rows = ('top', 'middle', 'bottom')
        where = ('a cell at the %s end of the select screen\'s %s row' % ('left' if cell['column'] < 10 else 'right',
                                                                         rows[cell['grid_row']])
                 if cell['column'] is not None else 'no cell (the select screen is full)')
        print('Done: %s has %s.' % (fighter, where))
    print('Start the game. The packs (in %s) hold Namco\'s assets: keep them for yourself.' % os.path.dirname(target))


if __name__ == '__main__':
    main()
