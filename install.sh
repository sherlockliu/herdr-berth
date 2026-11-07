#!/bin/sh
# Install Muster into the Herdr app and merge its key binding.
#   ./install.sh
# Removes the previous copy of the mod, keeps a backup of keys.json.
set -eu

SRC=$(cd "$(dirname "$0")" && pwd)
HOME_DIR=${HERDR_APP_HOME:-"$HOME/.config/herdr-app"}
DEST="$HOME_DIR/mods/muster"
CLI=$(command -v herdr-app || echo "$HOME/.local/bin/herdr-app")

[ -d "$HOME_DIR" ] || { echo "Herdr app home not found: $HOME_DIR" >&2; exit 1; }

mkdir -p "$HOME_DIR/mods"
rm -rf "$DEST"
cp -R "$SRC/mods/muster" "$DEST"
echo "copied -> $DEST"

python3 - "$SRC/keys.json" "$HOME_DIR/keys.json" <<'PY'
import json, shutil, sys
src, dest = sys.argv[1], sys.argv[2]
try:
    have = json.load(open(dest))
except FileNotFoundError:
    have = {}
want = json.load(open(src))
shutil.copyfile(dest, dest + ".bak-muster") if have else None
for section, keys in want.items():
    have.setdefault(section, {})
    for chord, action in keys.items():
        old = have[section].get(chord)
        if old and old != action:
            print(f"kept {chord}: {old} (wanted {action}) — bind it yourself if you prefer Muster")
        elif not old:
            have[section][chord] = action
            print(f"bound {chord} -> {action}")
json.dump(have, open(dest, "w"), indent=2)
PY

"$CLI" check "$DEST"
echo
echo "Open it with cmd-shift-o, or: $CLI do mod.open '{\"name\":\"muster\"}'"
