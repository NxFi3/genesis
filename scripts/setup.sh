#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11+ required"'
# Python runtime dependencies are standard-library only; no pip install is needed.
export XDG_DATA_HOME="${XDG_DATA_HOME:-$PWD/data/runtime/data}"
export XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$PWD/data/runtime/config}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$PWD/data/runtime/cache}"
mkdir -p "$XDG_DATA_HOME" "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME"
if command -v godot >/dev/null; then
    godot --version
elif command -v godot4 >/dev/null; then
    godot4 --version
else
    echo 'Godot 4.x is required for the graphical client. Headless Python remains available.' >&2
    exit 1
fi
python3 -m unittest discover -s tests -v
