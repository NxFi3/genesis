"""Atomic SQLite snapshots and queryable append-only event history."""
import json
import sqlite3
from pathlib import Path
from .world import World

SCHEMA = '''
CREATE TABLE IF NOT EXISTS saves (
    slot TEXT PRIMARY KEY, version INTEGER NOT NULL, tick INTEGER NOT NULL,
    state TEXT NOT NULL, saved_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS history (
    slot TEXT NOT NULL, event_id INTEGER NOT NULL, tick INTEGER NOT NULL,
    kind TEXT NOT NULL, event TEXT NOT NULL, PRIMARY KEY(slot, event_id)
);
'''


def save(world, path, slot='world'):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    state = json.dumps(world.snapshot(True), allow_nan=False)
    with sqlite3.connect(path, timeout=10) as db:
        db.executescript(SCHEMA)
        # Transactions preserve the preceding valid snapshot on interruption.
        db.execute('INSERT OR REPLACE INTO saves(slot,version,tick,state) VALUES(?,?,?,?)', (slot, 1, world.tick, state))
        # Rewinding a slot replaces its future history consistently.
        db.execute('DELETE FROM history WHERE slot=?', (slot,))
        db.executemany('INSERT INTO history VALUES(?,?,?,?,?)', [(slot, e['id'], e['tick'], e['kind'], json.dumps(e)) for e in world.events])


def load(path, slot='world'):
    if not Path(path).is_file():
        raise ValueError('Save does not exist')
    try:
        with sqlite3.connect(path) as db:
            row = db.execute('SELECT state FROM saves WHERE slot=?', (slot,)).fetchone()
        if not row:
            raise ValueError('Save slot does not exist')
        return World.from_snapshot(json.loads(row[0]))
    except (sqlite3.Error, json.JSONDecodeError, KeyError, TypeError, IndexError) as exc:
        raise ValueError(f'Cannot load save: {exc}') from exc
