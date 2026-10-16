"""Character packs: what the port loads to add a fighter (runtime/src/title/roster.cpp).

A pack is a folder `<code>/` in the characters folder ($TTT2_CHARACTERS, else ~/.local/share/ttt2/characters):
    character.ini              code = <three letters>, donor = <a TTT2 fighter's code>, sex = female | male
    <code>.xml                 item database (BXML)
    <code>.nud .nut .bon       body model, textures, skeleton
    <code>.moveset .motion     moveset (motbin) and motion pack
    <code>.mvl                 the practice command list (MVLT)
    se_Chr_<code>.nus3bank     its voice: shouts, damage voices and the announcer's call; win quotes (se_Dwi_);
    se_Dwi_<code>.nus3bank     intro lines (rm_Dst_); the long win quote one win pose streams (rm_Dwi_)
    rm_Dst_<code>.nus3bank
    rm_Dwi_<code>.nus3bank
    keys/<key>.bin             changed copies of the title's own entries (the costume palettes 9cdcd24f, a6e0a5e2
                               with the fighter's colours, 2D layouts with its pictures, ...)
    keys/<key>.add             texture pages added to one of the title's texture containers
    art/                       its pictures for the loading and VS screens (the port shows its art when the pack
                               has this folder)
Files a pack leaves out (<code>.mop, .havok.xml: spring bones and cloth collision; <code>.mvl: the practice
command list; the sound banks) are the donor's. A pack holds the other game's assets: it is for the player's own use only.
"""
import os

FILES = ('.xml', '.nud', '.nut', '.bon', '.moveset', '.motion')
SELECT_ID = 61                  # the select id the port gives the added fighter (roster.cpp kId): palette entries


def default_folder():
    if os.environ.get('TTT2_CHARACTERS'):
        return os.environ['TTT2_CHARACTERS']
    data = os.environ.get('XDG_DATA_HOME') or os.path.join(os.path.expanduser('~'), '.local', 'share')
    return os.path.join(data, 'ttt2', 'characters')


def character_ini(d):
    return ('# %s, from Tekken 7 (made on this machine from the player\'s own copy)\n'
            'code = %s\ndonor = %s\nsex = %s\n' % (d.NAME.split(' (')[0], d.CODE, d.DONOR, d.SEX))


def write(folder, d, files):
    """Writes the pack <folder>/<code>/ from files {suffix or file name: bytes} (a suffix starts with '.': the file
    is <code><suffix>); returns its path. Files of an earlier pack with the same names are replaced; nothing else in
    the folder is touched."""
    target = os.path.join(folder, d.CODE)
    os.makedirs(target, exist_ok=True)
    for name in files:
        if '/' in name:
            os.makedirs(os.path.join(target, os.path.dirname(name)), exist_ok=True)
    out = {'character.ini': character_ini(d).encode('utf-8')}
    out.update({(d.CODE + name if name.startswith('.') else name): data for name, data in files.items()})
    for name, data in out.items():
        sub, base = os.path.split(name)
        tmp = os.path.join(target, sub, '.' + base + '.part')
        with open(tmp, 'wb') as f:
            f.write(data)
        os.replace(tmp, os.path.join(target, name))
    return target
