#!/usr/bin/env python3
"""Adds a fighter from your own copy of Tekken 7 (PC) to Tekken Tag Tournament 2 (this repository's port).

Everything the fighter is made of is read from your files when you run this: your Tekken 7 installation, the
movesets you saved from it with TKMovesets2, and your installed Tekken Tag Tournament 2. The result is a character
pack in ~/.local/share/ttt2/characters/<code>/, which the game loads at start-up. The pack holds Namco's assets:
keep it for yourself, never upload or share it.

    python3 tools/characters/import_character.py kazumi \\
        --tekken7 "~/.local/share/Steam/steamapps/common/TEKKEN 7" \\
        --movesets ~/TKMovesets2/extracted_chars \\
        --game ~/Games/TekkenTag2

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
    parser.add_argument('fighter', help='who to add: kazumi')
    parser.add_argument('--tekken7', required=True, metavar='FOLDER',
                        help='your Tekken 7 PC installation (the folder holding TekkenGame/)')
    parser.add_argument('--movesets', required=True, metavar='FOLDER',
                        help='the folder with the fighter\'s and Heihachi\'s .tkmvst files (TKMovesets2)')
    parser.add_argument('--game', required=True, metavar='FOLDER',
                        help='your installed Tekken Tag Tournament 2 (the folder ttt2 --install made)')
    parser.add_argument('--out', metavar='FOLDER',
                        help='where character packs go (default: $TTT2_CHARACTERS, else ~/.local/share/ttt2/characters)')
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
    try:
        target = importer.run(args.fighter.lower(), os.path.expanduser(args.tekken7),
                              os.path.expanduser(args.movesets), os.path.expanduser(args.game),
                              args.out and os.path.expanduser(args.out))
    except InputError as error:
        sys.exit('import_character: %s' % error)
    print('Done. Start the game: the fighter has the cell at the right end of the select screen\'s top row.')
    print('The pack (%s) holds Namco\'s assets: keep it for yourself.' % target)


if __name__ == '__main__':
    main()
