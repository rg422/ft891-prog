"""A small FT-891 CAT emulator.

It implements the same transport interface as ``serial.Serial`` so the whole
program (and the test-suite) can run without a radio attached.  Select the
``SIMULATOR`` port in the GUI to use it.

The emulator answers ID, AI, EX, MR, MT, MW and FA.  Like the real radio it
only listens at the baud rate selected in menu 05-06 (CAT RATE).
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field, replace
from typing import Optional

from .cat import BAUD_RATES, FT891_ID
from .memory import (
    MemoryChannel,
    format_answer,
    is_writable,
    parse_memory_answer,
)
from .menu_defs import CAT_RATE, MENU_BY_NUMBER, MENU_ITEMS


def _seed_memories() -> dict[str, MemoryChannel]:
    mems = [
        MemoryChannel("001", 7_074_000, "DATA-U", tag="FT8 40M", tag_on=True),
        MemoryChannel("002", 14_074_000, "DATA-U", tag="FT8 20M", tag_on=True),
        MemoryChannel("003", 14_250_000, "USB"),
        MemoryChannel("004", 3_985_000, "LSB", tag="NET"),
        MemoryChannel("010", 29_620_000, "FM", ctcss="ENC", shift="MINUS", tag="10M RPT"),
        MemoryChannel("P1L", 7_000_000, "CW-U"),
        MemoryChannel("P1U", 7_125_000, "CW-U"),
        MemoryChannel("501", 5_330_500, "USB"),
        MemoryChannel("502", 5_346_500, "USB"),
        MemoryChannel("503", 5_357_000, "USB"),
        MemoryChannel("504", 5_371_500, "USB"),
        MemoryChannel("505", 5_403_500, "USB"),
        MemoryChannel("EMG", 5_167_500, "USB"),
    ]
    return {m.channel: m for m in mems}


def _default_menu() -> dict[str, str]:
    values = {}
    for item in MENU_ITEMS:
        raw = item.default if item.default is not None else 0
        if item.group == 18:
            raw = {"1801": 104, "1802": 103, "1803": 102}[item.number]
        values[item.number] = item.encode(raw)
    return values


@dataclass
class RadioState:
    """Persistent "radio" contents shared by all simulator connections."""

    menu: dict[str, str] = field(default_factory=_default_menu)
    memories: dict[str, MemoryChannel] = field(default_factory=_seed_memories)
    vfo_a: int = 14_074_000
    mt_read_supported: bool = True

    @property
    def cat_baud(self) -> int:
        return BAUD_RATES[int(self.menu[CAT_RATE])]


_shared_state: Optional[RadioState] = None


def shared_state() -> RadioState:
    global _shared_state
    if _shared_state is None:
        _shared_state = RadioState()
    return _shared_state


class SimulatedRadio:
    """Transport that behaves like an FT-891 on the other end of a serial cable."""

    def __init__(self, baudrate: int = 4800, state: Optional[RadioState] = None,
                 latency: float = 0.0):
        self.baudrate = baudrate
        self.state = state or shared_state()
        self.latency = latency
        self.received: list[str] = []
        self._in = bytearray()
        self._out = bytearray()
        self._lock = threading.Lock()
        self.ai = False

    # ----------------------------------------------------- transport API
    @property
    def in_waiting(self) -> int:
        with self._lock:
            return len(self._out)

    def read(self, size: int = 1) -> bytes:
        deadline = time.monotonic() + 0.05
        while True:
            with self._lock:
                if self._out:
                    chunk = bytes(self._out[:size])
                    del self._out[:size]
                    return chunk
            if time.monotonic() >= deadline:
                return b""
            time.sleep(0.002)

    def write(self, data: bytes) -> int:
        if self.baudrate != self.state.cat_baud:
            return len(data)  # wrong baud rate: the radio just sees noise
        self._in += data
        while b";" in self._in:
            idx = self._in.index(b";")
            cmd = self._in[:idx].decode("ascii", errors="replace")
            del self._in[: idx + 1]
            self.received.append(cmd + ";")
            if self.latency:
                time.sleep(self.latency)
            answer = self._handle(cmd)
            if answer:
                with self._lock:
                    self._out += answer.encode("ascii")
        return len(data)

    def reset_input_buffer(self) -> None:
        with self._lock:
            self._out.clear()

    def close(self) -> None:
        pass

    # ------------------------------------------------------ command logic
    def _handle(self, cmd: str) -> Optional[str]:
        name, body = cmd[:2].upper(), cmd[2:]
        handler = getattr(self, f"_cmd_{name}", None)
        if handler is None:
            return "?;"
        return handler(body)

    def _cmd_ID(self, body: str) -> Optional[str]:
        return f"ID{FT891_ID};" if body == "" else "?;"

    def _cmd_AI(self, body: str) -> Optional[str]:
        if body == "":
            return f"AI{int(self.ai)};"
        if body in ("0", "1"):
            self.ai = body == "1"
            return None
        return "?;"

    def _cmd_FA(self, body: str) -> Optional[str]:
        if body == "":
            return f"FA{self.state.vfo_a:09d};"
        if len(body) == 9 and body.isdigit():
            self.state.vfo_a = int(body)
            return None
        return "?;"

    def _cmd_EX(self, body: str) -> Optional[str]:
        num, p2 = body[:4], body[4:]
        if num not in self.state.menu:
            return "?;"
        if p2 == "":
            return f"EX{num}{self.state.menu[num]};"
        item = MENU_BY_NUMBER[num]
        current = self.state.menu[num]
        if item.readonly or len(p2) != len(current):
            return "?;"
        try:
            raw = item.decode(p2)
        except ValueError:
            return "?;"
        if not item.is_valid(raw) or (item.signed and p2[0] not in "+-"):
            return "?;"
        # Writing CAT RATE switches the listening baud rate immediately (see cat_baud).
        self.state.menu[num] = p2
        return None

    def _cmd_MR(self, body: str) -> Optional[str]:
        mem = self.state.memories.get(body.upper())
        return format_answer(mem, "MR") if mem else "?;"

    def _cmd_MT(self, body: str) -> Optional[str]:
        if len(body) == 3:  # read
            mem = self.state.memories.get(body.upper())
            if mem is None or not self.state.mt_read_supported:
                return "?;"
            return format_answer(mem, "MT")
        return self._store("MT" + body, expected_len=38)

    def _cmd_MW(self, body: str) -> Optional[str]:
        return self._store("MW" + body, expected_len=25)

    def _store(self, cmd: str, expected_len: int) -> Optional[str]:
        if len(cmd) - 2 != expected_len:
            return "?;"
        try:
            mem = parse_memory_answer(cmd)
        except ValueError:
            return "?;"
        if not is_writable(mem.channel) or mem.validate():
            return "?;"
        if cmd.startswith("MW"):
            old = self.state.memories.get(mem.channel)
            if old is not None:  # MW leaves the existing tag alone
                mem = replace(mem, tag=old.tag, tag_on=old.tag_on)
        self.state.memories[mem.channel] = mem
        return None
