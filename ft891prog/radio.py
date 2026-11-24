"""High-level FT-891 operations built on :class:`~ft891prog.cat.CatConnection`."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Iterable, Optional

from .cat import BAUD_RATES, CatConnection, CatError, CatRejected, CatTimeout
from .memory import (
    MemoryChannel,
    channel_label,
    format_mt,
    format_mw,
    is_writable,
    parse_memory_answer,
)
from .menu_defs import CAT_RATE, MENU_BY_NUMBER, VERSION_ITEMS, MenuItem, format_version

ProgressFn = Callable[[int, int, str], None]


class OperationCancelled(Exception):
    pass


class VerifyError(CatError):
    """The radio accepted a write but reads back a different value."""


@dataclass
class OpResult:
    key: str          # menu number or channel
    ok: bool
    message: str = ""


def _noop_progress(done: int, total: int, msg: str) -> None:
    pass


def _check_cancel(cancel: Optional[threading.Event]) -> None:
    if cancel is not None and cancel.is_set():
        raise OperationCancelled()


class FT891:
    """Menu and memory access for a connected FT-891."""

    def __init__(self, cat: CatConnection):
        self.cat = cat
        # P2 widths actually returned by the radio, keyed by menu number.  Used
        # when writing so we always match the radio's own format.
        self.menu_widths: dict[str, int] = {}
        # None = unknown yet, True/False once we tried "MTnnn;" as a read command.
        self.tag_read_supported: Optional[bool] = None
        self.radio_id: Optional[str] = None
        self.versions: dict[str, Optional[int]] = {}

    # ----------------------------------------------------------- session
    def identify(self) -> str:
        ans = self.cat.query("ID;", "ID")
        self.radio_id = ans[2:]
        return self.radio_id

    def prepare(self) -> None:
        """Turn off auto-information so the radio only talks when asked."""
        self.cat.set("AI0;")

    def _still_alive(self, exc: CatTimeout) -> None:
        """After a timeout on one item, re-raise unless the radio still answers ``ID;``."""
        try:
            self.cat.query("ID;", "ID")
        except CatError:
            raise exc from None

    def read_versions(self) -> str:
        parts = []
        for item in VERSION_ITEMS:
            try:
                raw = item.decode(self.read_menu_raw(item.number))
            except CatError:
                raw = None
            self.versions[item.number] = raw
            parts.append(f"{item.name.split()[0]} {format_version(raw)}")
        return ", ".join(parts)

    # -------------------------------------------------------------- menus
    def read_menu_raw(self, number: str) -> str:
        ans = self.cat.query(f"EX{number};", f"EX{number}")
        p2 = ans[6:]
        self.menu_widths[number] = len(p2)
        return p2

    def read_menu(self, item: MenuItem) -> int:
        return item.decode(self.read_menu_raw(item.number))

    def write_menu(self, item: MenuItem, raw: int) -> int:
        """Write one menu item and verify it by reading it back."""
        if item.readonly:
            raise ValueError(f"{item.label} {item.name} is read only")
        if not item.is_valid(raw):
            raise ValueError(f"{item.label} {item.name}: {item.display(raw)} is not a legal value")
        if item.number not in self.menu_widths:
            # Learn the exact P2 width the radio uses before writing anything.
            self.read_menu_raw(item.number)
        width = self.menu_widths.get(item.number, item.digits)
        p2 = item.encode(raw, width)
        ans, rejected = self.cat.set_and_read(f"EX{item.number}{p2};", f"EX{item.number};", f"EX{item.number}")
        back = item.decode(ans[6:])
        self.menu_widths[item.number] = len(ans) - 6
        if back != raw:
            why = "radio rejected the command" if rejected else "radio kept a different value"
            raise VerifyError(f"{item.label} {item.name}: wrote {item.display(raw)}, "
                              f"read back {item.display(back)} ({why})")
        return back

    def read_menus(self, items: Iterable[MenuItem], progress: ProgressFn = _noop_progress,
                   cancel: Optional[threading.Event] = None) -> tuple[dict[str, int], list[OpResult]]:
        items = list(items)
        values: dict[str, int] = {}
        problems: list[OpResult] = []
        for i, item in enumerate(items):
            _check_cancel(cancel)
            progress(i, len(items), f"Reading menu {item.label} {item.name}")
            try:
                values[item.number] = self.read_menu(item)
            except CatTimeout as exc:
                self._still_alive(exc)
                problems.append(OpResult(item.number, False, str(exc)))
            except (CatError, ValueError) as exc:
                problems.append(OpResult(item.number, False, str(exc)))
        progress(len(items), len(items), "Menu read complete")
        return values, problems

    def write_menus(self, changes: list[tuple[MenuItem, int]], progress: ProgressFn = _noop_progress,
                    cancel: Optional[threading.Event] = None) -> list[OpResult]:
        """Write several menu items.  CAT RATE (05-06) is always written last."""
        ordered = [c for c in changes if c[0].number != CAT_RATE]
        cat_rate = [c for c in changes if c[0].number == CAT_RATE]
        results: list[OpResult] = []
        total = len(changes)
        for i, (item, raw) in enumerate(ordered):
            _check_cancel(cancel)
            progress(i, total, f"Writing menu {item.label} {item.name} = {item.display(raw)}")
            try:
                self.write_menu(item, raw)
                results.append(OpResult(item.number, True, item.display(raw)))
            except CatTimeout as exc:
                self._still_alive(exc)
                results.append(OpResult(item.number, False, str(exc)))
            except (CatError, ValueError) as exc:
                results.append(OpResult(item.number, False, str(exc)))
        for item, raw in cat_rate:
            _check_cancel(cancel)
            progress(total - 1, total, f"Changing CAT RATE to {item.display(raw)}")
            results.append(self._write_cat_rate(item, raw))
        progress(total, total, "Menu write complete")
        return results

    def _write_cat_rate(self, item: MenuItem, raw: int) -> OpResult:
        new_baud = BAUD_RATES[raw]
        if new_baud == self.cat.baudrate:
            try:
                self.write_menu(item, raw)
                return OpResult(item.number, True, item.display(raw))
            except (CatError, ValueError) as exc:
                return OpResult(item.number, False, str(exc))
        width = self.menu_widths.get(item.number, item.digits)
        old_baud = self.cat.baudrate
        self.cat.set(f"EX{item.number}{item.encode(raw, width)};")
        time.sleep(0.3)
        self.cat.change_baudrate(new_baud)
        try:
            back = self.read_menu(item)
        except CatError:
            self.cat.change_baudrate(old_baud)
            return OpResult(item.number, False,
                            f"radio did not answer at {new_baud} bps after changing CAT RATE; "
                            f"still using {old_baud} bps")
        if back != raw:
            return OpResult(item.number, False, f"CAT RATE reads back {item.display(back)}")
        return OpResult(item.number, True, f"{item.display(raw)} (now connected at {new_baud} bps)")

    # ----------------------------------------------------------- memories
    def read_memory(self, ch: str) -> Optional[MemoryChannel]:
        """Read one channel; returns None if the channel is empty / not present."""
        try:
            ans = self.cat.query(f"MR{ch};", "MR")
        except CatRejected:
            return None
        mem = parse_memory_answer(ans).with_channel(ch)
        if self.tag_read_supported is not False:
            try:
                tagged = parse_memory_answer(self.cat.query(f"MT{ch};", "MT")).with_channel(ch)
                self.tag_read_supported = True
                mem = tagged
            except (CatRejected, CatTimeout, ValueError):
                # The CAT command table lists MT as set-only; if the radio does not
                # answer it as a read command, stop asking for tags.
                if self.tag_read_supported is None:
                    self.tag_read_supported = False
        return mem

    def write_memory(self, mem: MemoryChannel) -> MemoryChannel:
        """Write one channel (MT when a tag is involved, otherwise MW) and verify it."""
        if not is_writable(mem.channel):
            raise ValueError(f"channel {channel_label(mem.channel)} is read only")
        use_tag = self.tag_read_supported is not False or bool(mem.tag.strip()) or mem.tag_on
        cmd = format_mt(mem) if use_tag else format_mw(mem)
        ans, rejected = self.cat.set_and_read(cmd, f"MR{mem.channel};", "MR", settle=0.1)
        if rejected and use_tag:
            # Fall back to MW (no tag) if the radio does not accept MT.
            ans, rejected = self.cat.set_and_read(format_mw(mem), f"MR{mem.channel};", "MR", settle=0.1)
            if not rejected:
                self.tag_read_supported = False
        back = parse_memory_answer(ans).with_channel(mem.channel)
        if self.tag_read_supported:
            try:
                back = parse_memory_answer(self.cat.query(f"MT{mem.channel};", "MT")).with_channel(mem.channel)
            except CatError:
                pass
        if not mem.same_radio_data(back, compare_tag=bool(self.tag_read_supported)):
            why = " (radio rejected the command)" if rejected else ""
            raise VerifyError(f"channel {channel_label(mem.channel)}: read-back differs{why}")
        return back

    def read_memories(self, channels: Iterable[str], progress: ProgressFn = _noop_progress,
                      cancel: Optional[threading.Event] = None
                      ) -> tuple[dict[str, Optional[MemoryChannel]], list[OpResult]]:
        channels = list(channels)
        result: dict[str, Optional[MemoryChannel]] = {}
        problems: list[OpResult] = []
        for i, ch in enumerate(channels):
            _check_cancel(cancel)
            progress(i, len(channels), f"Reading memory {channel_label(ch)}")
            try:
                result[ch] = self.read_memory(ch)
            except CatTimeout as exc:
                self._still_alive(exc)
                problems.append(OpResult(ch, False, str(exc)))
            except (CatError, ValueError) as exc:
                problems.append(OpResult(ch, False, str(exc)))
        progress(len(channels), len(channels), "Memory read complete")
        return result, problems

    def write_memories(self, mems: list[MemoryChannel], progress: ProgressFn = _noop_progress,
                       cancel: Optional[threading.Event] = None) -> list[OpResult]:
        results: list[OpResult] = []
        for i, mem in enumerate(mems):
            _check_cancel(cancel)
            progress(i, len(mems), f"Writing memory {channel_label(mem.channel)}")
            try:
                self.write_memory(mem)
                results.append(OpResult(mem.channel, True))
            except CatTimeout as exc:
                self._still_alive(exc)
                results.append(OpResult(mem.channel, False, str(exc)))
            except (CatError, ValueError) as exc:
                results.append(OpResult(mem.channel, False, str(exc)))
        progress(len(mems), len(mems), "Memory write complete")
        return results


def menu_item(number: str) -> MenuItem:
    return MENU_BY_NUMBER[number]
