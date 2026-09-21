#!/usr/bin/env python3
"""
Backport ORAS mega evolutions into a Pokemon X/Y romhack.

Extracts mega data from YOUR OWN copy of Omega Ruby / Alpha Sapphire and applies
it to YOUR OWN copy of X/Y. No game data is distributed with this script.

    python3 backport_megas.py --oras <ORAS romfs> --xy <XY romfs> --out <out dir>

Both paths are extracted RomFS directories. Output is a romfs tree to install as
a LayeredFS mod.

Requires garcw.py alongside this file.
"""
import argparse, os, struct, sys
import garcw

# ---- archive paths -------------------------------------------------------
ORAS_PERSONAL, ORAS_MEGAEVO = "a/1/9/5", "a/1/9/3"
XY_LEARNSET, XY_EVO, XY_MEGAEVO, XY_PERSONAL = "a/2/1/4", "a/2/1/5", "a/2/1/6", "a/2/1/8"
XY_ITEMS = "a/2/2/0"
XY_TEXT_SLOTS = ["a/0/7/%d" % n for n in range(2, 10)]
ITEM_TEXT_SUBFILES = (95, 96, 97, 98, 99)

# Mega-specific fields copied from ORAS; everything else stays as YOUR build has it,
# so your own stat/type/TM edits survive.
MEGA_FIELDS = (list(range(0x00, 0x08)) + [0x0A, 0x0B] + [0x18, 0x19, 0x1A]
               + [0x21] + list(range(0x22, 0x28)))

STONE_NAMES = {
    3:"Venusaurite",   6:"Charizardite X", 9:"Blastoisinite", 15:"Beedrillite",
    18:"Pidgeotite",   65:"Alakazite",     80:"Slowbronite",  94:"Gengarite",
    115:"Kangaskhanite",127:"Pinsirite",   130:"Gyaradosite", 142:"Aerodactylite",
    150:"Mewtwonite X",181:"Ampharosite",  208:"Steelixite",  212:"Scizorite",
    214:"Heracronite", 229:"Houndoominite",248:"Tyranitarite",254:"Sceptilite",
    257:"Blazikenite", 260:"Swampertite",  282:"Gardevoirite",302:"Sablenite",
    303:"Mawilite",    306:"Aggronite",    308:"Medichamite", 310:"Manectite",
    319:"Sharpedonite",323:"Cameruptite",  334:"Altarianite", 354:"Banettite",
    359:"Absolite",    362:"Glalitite",    373:"Salamencite", 376:"Metagrossite",
    380:"Latiasite",   381:"Latiosite",    428:"Lopunnite",   445:"Garchompite",
    448:"Lucarionite", 460:"Abomasite",    475:"Galladite",   531:"Audinite",
    719:"Diancite",
}
SPECIES_NAMES = {
    3:"Venusaur",   6:"Charizard",  9:"Blastoise",  15:"Beedrill",  18:"Pidgeot",
    65:"Alakazam",  80:"Slowbro",   94:"Gengar",   115:"Kangaskhan",127:"Pinsir",
    130:"Gyarados",142:"Aerodactyl",150:"Mewtwo",  181:"Ampharos", 208:"Steelix",
    212:"Scizor",  214:"Heracross", 229:"Houndoom",248:"Tyranitar",254:"Sceptile",
    257:"Blaziken",260:"Swampert",  282:"Gardevoir",302:"Sableye", 303:"Mawile",
    306:"Aggron",  308:"Medicham",  310:"Manectric",319:"Sharpedo",323:"Camerupt",
    334:"Altaria", 354:"Banette",   359:"Absol",   362:"Glalie",   373:"Salamence",
    376:"Metagross",380:"Latias",   381:"Latios",  428:"Lopunny",  445:"Garchomp",
    448:"Lucario", 460:"Abomasnow", 475:"Gallade", 531:"Audino",   719:"Diancie",
}
DESC = ("One variety of the mysterious Mega Stones.\n"
        "Have {mon} hold it, and this stone will\n"
        "enable it to Mega Evolve during battle.")

# ---- text codec ----------------------------------------------------------
KEY_BASE, KEY_STEP = 0x7C89, 0x2983
PLURAL_VAR = [0x10, 0x03, 0x1101, 0x00FE, 0x0100]   # copied verbatim from vanilla

def text_parse(b):
    nsec, nline, tot, init = struct.unpack_from('<HHII', b, 0)
    if nsec != 1:
        raise ValueError("unexpected section count %d" % nsec)
    so, = struct.unpack_from('<I', b, 12)
    slen, = struct.unpack_from('<I', b, so)
    ents = []
    for i in range(nline):
        off, ln, flg = struct.unpack_from('<IHH', b, so + 4 + i * 8)
        ents.append([b[so + off:so + off + ln * 2], flg])
    return {"init": init, "so": so, "ents": ents}

def text_build(g):
    ents, so = g["ents"], g["so"]
    doff = 4 + len(ents) * 8
    tbl, body = bytearray(), bytearray()
    for raw, flg in ents:
        tbl += struct.pack('<IHH', doff + len(body), len(raw) // 2, flg)
        body += raw
        while (doff + len(body)) % 4:
            body += b'\x00'
    slen = doff + len(body)
    out = bytearray()
    out += struct.pack('<HHII', 1, len(ents), slen, g["init"])
    out += struct.pack('<I', so) + struct.pack('<I', slen) + tbl + body
    return bytes(out)

def text_encode(tokens, line_index):
    k = (KEY_BASE + line_index * KEY_STEP) & 0xFFFF
    out = bytearray()
    for c in list(tokens) + [0]:
        out += struct.pack('<H', c ^ k)
        k = ((k << 3) | (k >> 13)) & 0xFFFF
    return bytes(out)

def toks(s):
    return [ord(c) for c in s]

# ---- helpers -------------------------------------------------------------
def load(root, rel):
    p = os.path.join(root, rel)
    if not os.path.isfile(p):
        sys.exit("missing archive: %s" % p)
    return garcw.parse(open(p, 'rb').read())

def blobs(g):
    return [e[1][0][1] for e in g["entries"]]

def save(root, rel, data):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, 'wb').write(data)

def records(blob, size):
    return [bytearray(blob[i * size:(i + 1) * size]) for i in range(len(blob) // size)]

# ---- main ----------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--oras", required=True, help="extracted ORAS RomFS")
    ap.add_argument("--xy", required=True, help="extracted X/Y RomFS (your build)")
    ap.add_argument("--out", required=True, help="output romfs directory")
    ap.add_argument("--price", type=int, default=1000,
                    help="stone price / 10 (default 1000 = 10,000)")
    ap.add_argument("--icon", type=lambda x: int(x, 0), default=0xD8,
                    help="item icon index for new stones")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    o_per = blobs(load(a.oras, ORAS_PERSONAL))
    o_meg = blobs(load(a.oras, ORAS_MEGAEVO))
    g4, g5, g6 = (load(a.xy, XY_LEARNSET), load(a.xy, XY_EVO), load(a.xy, XY_MEGAEVO))
    g8, gi = load(a.xy, XY_PERSONAL), load(a.xy, XY_ITEMS)

    oR = records(o_per[-1], 80)
    xR = records(blobs(g8)[-1], 64)
    print("ORAS personal %d records | XY personal %d records | XY items %d"
          % (len(oR), len(xR), len(gi["entries"])))

    # species that have a mega in ORAS but not yet in this XY build
    todo = []
    for sp in range(1, min(len(oR), len(xR))):
        om = o_meg[sp] if sp < len(o_meg) else b''
        xm = g6["entries"][sp][1][0][1] if sp < len(g6["entries"]) else b''
        o_method = struct.unpack_from('<HHHH', om, 0)[1] if len(om) >= 8 else 0
        x_method = struct.unpack_from('<HHHH', xm, 0)[1] if len(xm) >= 8 else 0
        if o_method and not x_method:
            todo.append((sp, struct.unpack_from('<HHHH', om, 0)))
    if not todo:
        print("nothing to add — every ORAS mega already present")
        return
    print("adding %d megas: %s" % (len(todo),
          ", ".join(STONE_NAMES.get(s, "sp%d" % s) for s, _ in todo)))
    if a.dry_run:
        return

    next_item = len(gi["entries"])
    item_tmpl = None
    for sp in STONE_NAMES:                      # template from an existing stone
        xm = g6["entries"][sp][1][0][1] if sp < len(g6["entries"]) else b''
        if len(xm) >= 8:
            iid = struct.unpack_from('<HHHH', xm, 0)[2]
            if 0 < iid < len(gi["entries"]):
                item_tmpl = bytearray(gi["entries"][iid][1][0][1]); break
    if item_tmpl is None:
        sys.exit("could not find an existing mega stone to use as an item template")
    struct.pack_into('<H', item_tmpl, 0, a.price)
    item_tmpl[0x0F] = a.icon

    new_stones = []
    for sp, (form, method, arg, _x) in todo:
        slot = len(xR)
        o_fsi, = struct.unpack_from('<H', oR[sp], 0x1C)
        mega = oR[o_fsi + form - 1]
        rec = bytearray(xR[sp])                 # keep YOUR base record
        for off in MEGA_FIELDS:
            rec[off] = mega[off]                # overwrite only mega fields
        struct.pack_into('<H', rec, 0x1C, 0)
        rec[0x20] = 1
        xR.append(rec)
        struct.pack_into('<H', xR[sp], 0x1C, slot)
        xR[sp][0x20] = 2

        src = g4["entries"][sp][1][0][1]        # copy base learnset, as vanilla does
        g4["entries"].append((1, [(0, src, len(src))]))
        g5["entries"].append((1, [(0, b'\x00' * 48, 48)]))
        g6["entries"].append((1, [(0, b'\x00' * 24, 24)]))

        e = bytearray(24)
        if method == 1:
            struct.pack_into('<HHHH', e, 0, form, 1, next_item, 0)
            new_stones.append((sp, next_item)); next_item += 1
            gi["entries"].append((1, [(0, bytes(item_tmpl), len(item_tmpl))]))
        else:
            struct.pack_into('<HHHH', e, 0, form, method, 0, 0)
        g6["entries"][sp] = (1, [(0, bytes(e), 24)])
        print("  sp%-4d slot %-4d %s" % (sp, slot,
              "item %d" % (next_item - 1) if method == 1 else "method %d" % method))

    ent = [(1, [(0, bytes(r), 64)]) for r in xR]
    nb = b''.join(bytes(r) for r in xR)
    ent.append((1, [(0, nb, len(nb))]))
    g8b = dict(g8); g8b["entries"] = ent

    save(a.out, XY_PERSONAL, garcw.build(g8b))
    save(a.out, XY_LEARNSET, garcw.build(g4))
    save(a.out, XY_EVO,      garcw.build(g5))
    save(a.out, XY_MEGAEVO,  garcw.build(g6))
    save(a.out, XY_ITEMS,    garcw.build(gi))

    # ---- item text, into every language slot ----
    # Each slot is a DIFFERENT language (vanilla: 2 JPN kana, 3 JPN kanji, 4 EN,
    # 5 FR, 6 IT, 7 DE, 8 ES, 9 KO). Every slot is read, extended and written back
    # on its own -- an earlier version loaded the first slot found and wrote it
    # into all eight, which on an unmodified romfs turned every language Japanese.
    found = [rel for rel in XY_TEXT_SLOTS if os.path.isfile(os.path.join(a.xy, rel))]
    if not found:
        print("! no text archive found - stones will be unnamed")
    for rel in found:
        src_text = load(a.xy, rel)
        fs = blobs(src_text); new = list(fs)
        for fi in ITEM_TEXT_SUBFILES:
            t = text_parse(fs[fi])
            for sp, iid in new_stones:
                while len(t["ents"]) < iid:
                    t["ents"].append([text_encode([], len(t["ents"])), 0])
                name = STONE_NAMES.get(sp, "Mega Stone")
                i = len(t["ents"])
                if fi == 95:   tok = toks(name) + PLURAL_VAR + toks("s")
                elif fi == 97: tok = toks(name + "s")
                elif fi == 99: tok = toks(DESC.format(
                                   mon=SPECIES_NAMES.get(sp, "this Pokemon")))
                else:          tok = toks(name)
                t["ents"].append([text_encode(tok, i), 0])
            new[fi] = text_build(t)
        g2 = dict(src_text); g2["entries"] = [(1, [(0, b, len(b))]) for b in new]
        save(a.out, rel, garcw.build(g2))

    print("\nwrote %s" % a.out)
    print("personal %d records | items %d" % (len(xR), len(gi["entries"])))
    print("Install as a LayeredFS mod. Mega models are NOT handled (a/0/0/7).")

if __name__ == "__main__":
    main()
