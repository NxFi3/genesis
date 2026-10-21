#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export XDG_DATA_HOME="${XDG_DATA_HOME:-$PWD/data/runtime/data}"
export XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$PWD/data/runtime/config}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$PWD/data/runtime/cache}"
mkdir -p "$XDG_DATA_HOME" "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME"
genesis_godot=$(command -v godot || command -v godot4)
"$genesis_godot" --headless --path godot --editor --import --quit
"$genesis_godot" --headless --path godot -- --smoke "--api=${1:-http://127.0.0.1:8765}"

"$genesis_godot" --headless --path godot --script res://tests/presentation_check.gd
