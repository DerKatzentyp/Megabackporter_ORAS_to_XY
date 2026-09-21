# ORAS Mega Backport for Pokemon X/Y

Adds Omega Ruby / Alpha Sapphire mega evolutions to an X/Y romhack.

**No game data is included here.** This script extracts what it needs from *your own*
copy of ORAS and applies it to *your own* copy of X/Y. Nothing copyrighted is
redistributed — you need both games.

## Usage

```
python3 backport_megas.py --oras <ORAS romfs> --xy <XY romfs> --out <output dir>
```

Both inputs are extracted RomFS directories (use a 3DS ROM tool of your choice).
The output is a `romfs` tree to install as a LayeredFS mod.

```
--price N     stone price / 10   (default 1000 = 10,000)
--icon  N     item icon index for new stones (default 0xD8)
--dry-run     list what would be added, change nothing
```

`garcw.py` must sit alongside the script.

## What it does

It finds every species with a mega in ORAS but not in your X/Y build, then:

1. **Grows four archives in lockstep** — `a/2/1/4` (learnsets), `a/2/1/5`
   (evolutions), `a/2/1/6` (mega evolutions) and `a/2/1/8` (personal). They are all
   indexed by the same form index and loaded together at boot; growing any one alone
   is an instant black screen. This is the crux of the whole thing.
2. **Builds each mega's personal record from YOUR base species record**, overwriting
   only the mega-specific fields from ORAS:
   `stats, types, EV yield, abilities, colour, base EXP, height, weight`.
   Your own stat edits, type edits, TM/HM flags and egg groups all survive.
3. **Gives each new form slot a copy of its base species' learnset**, and all-zero
   evolution and megaevo entries — matching what vanilla does for its own mega slots.
   Do not leave these empty: a real 3DS is far less forgiving than an emulator.
4. **Appends a mega stone item** per mega, priced (a price of 0 is a division by zero
   in the mart and crashes the game), and **names it in every language slot**.

ORAS's 80-byte personal records and XY's 64-byte ones share their first 0x40 bytes,
except `0x35` (a TM bitfield — the games have different TM lists). Copying only the
listed fields sidesteps that entirely.

## Rayquaza

Mega Rayquaza uses megaevo **method 2** (learn Dragon Ascent) and has no stone. The
script replicates that faithfully, but **XY has no Dragon Ascent**, so it stays inert
until the move is added. Everything else works unchanged.

## Not handled

- **Models.** Every mega shows its base species' sprite. That is `a/0/0/7` and a much
  larger job — model groups must be contiguous per species, so adding one means
  appending a copy of the base group plus the mega group and rewriting the species'
  4-byte index record.
- **Where to obtain the stones.** The script creates the items; putting them in a
  shop, on the ground, or in a save is up to you.
- **Item icons.** New stones reuse an existing stone's icon, so they all look alike.

## A warning about pk3DS and LayeredFS

pk3DS code edits that **grow** a table (adding a mart item, say) relocate the data
past the end of `.rodata`. The loader zero-fills that space, so the change silently
does nothing — no crash, no items. pk3DS assumes you will rebuild the ROM, where it
also grows the section in the exheader; an IPS over LayeredFS cannot touch the
exheader. In-place edits are fine. Rebuild the ROM for release.
