"""Editable in-memory state: what the user is editing vs. what the radio holds."""

from __future__ import annotations

from typing import Iterable, Optional

from .memory import ALL_CHANNELS, MemoryChannel, is_writable
from .menu_defs import MENU_BY_NUMBER, MENU_ITEMS, WRITABLE_ITEMS, MenuItem


class SettingsModel:
    """Menu values.

    ``values`` is what the user sees and edits; ``radio`` is the last value known
    to be in the radio (``None`` when it has not been read).  An item is
    *changed* when it differs from the radio.
    """

    def __init__(self) -> None:
        self.values: dict[str, Optional[int]] = {i.number: None for i in MENU_ITEMS}
        self.radio: dict[str, Optional[int]] = {i.number: None for i in MENU_ITEMS}

    def item(self, number: str) -> MenuItem:
        return MENU_BY_NUMBER[number]

    def set(self, number: str, raw: Optional[int]) -> None:
        item = self.item(number)
        if raw is not None and not item.is_valid(raw):
            raise ValueError(f"{item.label} {item.name}: illegal value {raw}")
        self.values[number] = raw

    def is_changed(self, number: str) -> bool:
        v = self.values.get(number)
        return v is not None and not self.item(number).readonly and v != self.radio.get(number)

    def changed_items(self) -> list[tuple[MenuItem, int]]:
        return [(i, self.values[i.number]) for i in WRITABLE_ITEMS if self.is_changed(i.number)]  # type: ignore[misc]

    def all_items(self) -> list[tuple[MenuItem, int]]:
        return [(i, self.values[i.number]) for i in WRITABLE_ITEMS if self.values[i.number] is not None]  # type: ignore[misc]

    def has_values(self) -> bool:
        return any(v is not None for v in self.values.values())

    def apply_radio(self, values: dict[str, int], keep_edits: bool = False) -> None:
        """Values just read from the radio.

        With ``keep_edits`` only the radio side is updated (a *compare*): the
        user's values stay, so differences show up as changes to write.
        """
        for number, raw in values.items():
            self.radio[number] = raw
            if not keep_edits or self.values.get(number) is None or self.item(number).readonly:
                self.values[number] = raw

    def mark_written(self, number: str, raw: int) -> None:
        self.radio[number] = raw

    def revert(self, numbers: Optional[Iterable[str]] = None) -> None:
        for number in numbers if numbers is not None else list(self.values):
            if self.radio.get(number) is not None:
                self.values[number] = self.radio[number]

    def load_defaults(self) -> None:
        for item in WRITABLE_ITEMS:
            if item.default is not None:
                self.values[item.number] = item.default

    def forget_radio(self) -> None:
        for number in self.radio:
            self.radio[number] = None

    def clear(self) -> None:
        for number in self.values:
            self.values[number] = None
            self.radio[number] = None


class MemoryModel:
    """Memory channel contents (``None`` = empty channel)."""

    def __init__(self) -> None:
        self.values: dict[str, Optional[MemoryChannel]] = {ch: None for ch in ALL_CHANNELS}
        self.radio: dict[str, Optional[MemoryChannel]] = {ch: None for ch in ALL_CHANNELS}
        self.radio_known: set[str] = set()
        self.compare_tags = True

    def set(self, ch: str, mem: Optional[MemoryChannel]) -> None:
        if mem is not None and mem.channel != ch:
            mem = mem.with_channel(ch)
        self.values[ch] = mem

    def get(self, ch: str) -> Optional[MemoryChannel]:
        return self.values.get(ch)

    def status(self, ch: str) -> str:
        """``""`` (unchanged), ``"new"``, ``"modified"``, ``"cleared"``, ``"unknown"``."""
        v = self.values.get(ch)
        if ch not in self.radio_known:
            return "unknown" if v is not None else ""
        r = self.radio.get(ch)
        if v is None and r is None:
            return ""
        if v is None:
            return "cleared"
        if r is None:
            return "new"
        return "" if v.same_radio_data(r, compare_tag=self.compare_tags) else "modified"

    def is_changed(self, ch: str) -> bool:
        return is_writable(ch) and self.status(ch) in ("new", "modified", "unknown")

    def changed_channels(self) -> list[MemoryChannel]:
        return [self.values[ch] for ch in ALL_CHANNELS if self.is_changed(ch)]  # type: ignore[misc]

    def all_channels(self) -> list[MemoryChannel]:
        return [m for ch, m in self.values.items() if m is not None and is_writable(ch)]

    def cleared_channels(self) -> list[str]:
        return [ch for ch in ALL_CHANNELS if is_writable(ch) and self.status(ch) == "cleared"]

    def apply_radio(self, data: dict[str, Optional[MemoryChannel]], keep_edits: bool = False) -> None:
        """Channels just read from the radio (``keep_edits`` = compare only)."""
        for ch, mem in data.items():
            self.radio[ch] = mem
            self.radio_known.add(ch)
            if not keep_edits or not is_writable(ch):
                self.values[ch] = mem

    def mark_written(self, ch: str, mem: MemoryChannel) -> None:
        self.radio[ch] = mem
        self.radio_known.add(ch)

    def revert(self, channels: Optional[Iterable[str]] = None) -> None:
        for ch in channels if channels is not None else list(self.values):
            if ch in self.radio_known:
                self.values[ch] = self.radio[ch]

    def forget_radio(self) -> None:
        self.radio = {ch: None for ch in ALL_CHANNELS}
        self.radio_known.clear()

    def clear(self) -> None:
        self.values = {ch: None for ch in ALL_CHANNELS}
        self.forget_radio()
