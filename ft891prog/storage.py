"""Saving and loading: JSON profiles (menus + memories) and memory CSV files."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from . import __version__
from .memory import (
    ALL_CHANNELS,
    CTCSS_TO_CODE,
    MODE_TO_CODE,
    SHIFT_TO_CODE,
    MemoryChannel,
    channel_from_label,
    channel_label,
    format_freq,
    parse_freq,
)
from .menu_defs import MENU_BY_NUMBER
from .model import MemoryModel, SettingsModel

PROFILE_FORMAT = "ft891prog-profile"
PROFILE_VERSION = 1
PROFILE_EXT = ".ft891.json"


# ------------------------------------------------------------------ profiles
def save_profile(path: Path, settings: SettingsModel, memories: MemoryModel,
                 radio_info: Optional[dict] = None) -> None:
    data = {
        "format": PROFILE_FORMAT,
        "version": PROFILE_VERSION,
        "saved": datetime.now().isoformat(timespec="seconds"),
        "program": f"ft891prog {__version__}",
        "radio": radio_info or {},
        "settings": {
            number: {"name": MENU_BY_NUMBER[number].name, "value": raw,
                     "display": MENU_BY_NUMBER[number].display(raw)}
            for number, raw in settings.values.items()
            if raw is not None and not MENU_BY_NUMBER[number].readonly
        },
        "memories": [m.to_dict() for ch, m in memories.values.items() if m is not None],
    }
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


def load_profile(path: Path, settings: SettingsModel, memories: MemoryModel) -> list[str]:
    """Load a profile into the models; returns a list of warnings.

    Radio-side state is forgotten, so everything loaded counts as "to be written".
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format") != PROFILE_FORMAT:
        raise ValueError(f"{path.name} is not an FT-891 Programmer profile")
    warnings: list[str] = []
    new_settings: dict[str, int] = {}
    for number, entry in data.get("settings", {}).items():
        item = MENU_BY_NUMBER.get(number)
        raw = entry.get("value") if isinstance(entry, dict) else entry
        if item is None or item.readonly:
            warnings.append(f"ignored unknown menu item {number}")
            continue
        if not isinstance(raw, int) or not item.is_valid(raw):
            warnings.append(f"ignored illegal value {raw!r} for {item.label} {item.name}")
            continue
        new_settings[number] = raw
    new_memories: dict[str, MemoryChannel] = {}
    for entry in data.get("memories", []):
        try:
            mem = MemoryChannel.from_dict(entry)
        except (KeyError, ValueError, TypeError) as exc:
            warnings.append(f"ignored memory entry: {exc}")
            continue
        if mem.channel not in ALL_CHANNELS:
            warnings.append(f"ignored unknown channel {mem.channel}")
            continue
        new_memories[mem.channel] = mem

    settings.clear()
    for number, raw in new_settings.items():
        settings.values[number] = raw
    memories.clear()
    for ch, mem in new_memories.items():
        memories.values[ch] = mem
    return warnings


# ----------------------------------------------------------------------- CSV
CSV_COLUMNS = ["Channel", "Frequency (MHz)", "Mode", "Tag", "Show Tag",
               "Clarifier", "Clar Offset (Hz)", "CTCSS", "Shift"]


def export_csv(path: Path, memories: MemoryModel) -> int:
    count = 0
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(CSV_COLUMNS)
        for ch in ALL_CHANNELS:
            m = memories.values.get(ch)
            if m is None:
                continue
            w.writerow([channel_label(ch), format_freq(m.freq_hz), m.mode, m.tag,
                        "Y" if m.tag_on else "N", "ON" if m.clar_on else "OFF",
                        m.clar_offset_hz, m.ctcss, m.shift])
            count += 1
    return count


def _truthy(text: str) -> bool:
    return text.strip().lower() in ("y", "yes", "1", "true", "on", "tag")


def import_csv(path: Path) -> tuple[dict[str, MemoryChannel], list[str]]:
    """Read a CSV file; returns ``(channels, warnings)``.  Does not touch the model."""
    result: dict[str, MemoryChannel] = {}
    warnings: list[str] = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("CSV file is empty")
        cols = {name.strip().lower(): name for name in reader.fieldnames}

        def col(row: dict, *names: str, default: str = "") -> str:
            for n in names:
                key = cols.get(n.lower())
                if key is not None and row.get(key) not in (None, ""):
                    return str(row[key]).strip()
            return default

        for lineno, row in enumerate(reader, start=2):
            try:
                ch = channel_from_label(col(row, "Channel", "Ch", "Memory"))
                freq = parse_freq(col(row, "Frequency (MHz)", "Frequency", "Freq"))
                mode = col(row, "Mode", default="USB").upper()
                if mode not in MODE_TO_CODE:
                    raise ValueError(f"unknown mode {mode!r}")
                ctcss = col(row, "CTCSS", "Tone", default="OFF").upper()
                if ctcss not in CTCSS_TO_CODE:
                    raise ValueError(f"unknown CTCSS {ctcss!r}")
                shift = col(row, "Shift", "Duplex", default="SIMPLEX").upper()
                shift = {"+": "PLUS", "-": "MINUS", "": "SIMPLEX", "OFF": "SIMPLEX"}.get(shift, shift)
                if shift not in SHIFT_TO_CODE:
                    raise ValueError(f"unknown shift {shift!r}")
                mem = MemoryChannel(
                    channel=ch,
                    freq_hz=freq,
                    mode=mode,
                    clar_on=_truthy(col(row, "Clarifier", "Clar", default="OFF")),
                    clar_offset_hz=int(float(col(row, "Clar Offset (Hz)", "Clar Offset", default="0"))),
                    ctcss=ctcss,
                    shift=shift,
                    tag=col(row, "Tag", "Name", default=""),
                    tag_on=_truthy(col(row, "Show Tag", "Tag On", default="N")),
                )
                errors = mem.validate()
                if errors:
                    raise ValueError("; ".join(errors))
                result[ch] = mem
            except ValueError as exc:
                warnings.append(f"line {lineno}: {exc}")
    return result, warnings
