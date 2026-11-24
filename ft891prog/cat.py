"""Low-level CAT transport for the Yaesu FT-891.

The FT-891 speaks Yaesu's ASCII "new CAT" protocol: two-letter commands, fixed
width parameters and a ``;`` terminator.  Set commands produce no answer when
they succeed; the radio answers ``?;`` when it rejects a command.  Read commands
return an answer that starts with the same two letters.

This module only knows about framing, timing and error handling.  The meaning
of individual commands lives in :mod:`ft891prog.radio`.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional, Protocol

BAUD_RATES = (4800, 9600, 19200, 38400)
FT891_ID = "0650"
SIMULATOR_PORT = "SIMULATOR"

TraceFn = Callable[[str, str], None]


class CatError(Exception):
    """Base class for CAT communication problems."""


class CatTimeout(CatError):
    """The radio did not answer in time."""

    def __init__(self, cmd: str):
        super().__init__(f"No answer from radio to {cmd!r} (check port, baud rate and that the radio is on)")
        self.cmd = cmd


class CatRejected(CatError):
    """The radio answered ``?;`` (command rejected / not available)."""

    def __init__(self, cmd: str):
        super().__init__(f"Radio rejected command {cmd!r}")
        self.cmd = cmd


class Transport(Protocol):
    """The subset of ``serial.Serial`` used by :class:`CatConnection`."""

    baudrate: int

    @property
    def in_waiting(self) -> int: ...

    def write(self, data: bytes) -> Optional[int]: ...

    def read(self, size: int = 1) -> bytes: ...

    def reset_input_buffer(self) -> None: ...

    def close(self) -> None: ...


@dataclass
class SerialOptions:
    port: str
    baudrate: int = 4800
    stopbits: int = 2
    rts: bool = True   # FT-891 menu 05-08 CAT RTS (default ENABLE) watches this line
    dtr: bool = False  # DTR can key PTT/CW on the radio, so keep it low by default
    timeout: float = 1.0


def list_serial_ports() -> list[tuple[str, str]]:
    """Return ``(device, description)`` for every serial port on the system."""
    try:
        from serial.tools import list_ports
    except ImportError:  # pragma: no cover - pyserial is a hard dependency
        return []
    ports = []
    for p in list_ports.comports():
        ports.append((p.device, p.description or ""))

    def sort_key(item: tuple[str, str]):
        dev = item[0]
        digits = "".join(ch for ch in dev if ch.isdigit())
        return (dev.rstrip("0123456789"), int(digits) if digits else 0)

    return sorted(ports, key=sort_key)


def guess_cat_port(ports: list[tuple[str, str]]) -> Optional[str]:
    """Pick the FT-891 CAT port.

    The radio's CP2105 bridge exposes two ports: the *Enhanced* COM port carries
    CAT commands, the *Standard* COM port is for PTT/CW keying.
    """
    for dev, desc in ports:
        if "enhanced" in desc.lower():
            return dev
    for dev, desc in ports:
        if "cp210" in desc.lower():
            return dev
    return ports[0][0] if ports else None


def open_serial(opts: SerialOptions) -> Transport:
    """Open a serial port configured for the FT-891 CAT interface."""
    import serial

    ser = serial.Serial()
    ser.port = opts.port
    ser.baudrate = opts.baudrate
    ser.bytesize = serial.EIGHTBITS
    ser.parity = serial.PARITY_NONE
    ser.stopbits = serial.STOPBITS_TWO if opts.stopbits == 2 else serial.STOPBITS_ONE
    ser.timeout = 0.05
    ser.write_timeout = max(1.0, opts.timeout)
    ser.xonxoff = False
    ser.rtscts = False
    ser.dsrdtr = False
    # Set the control lines *before* opening so they never glitch on open.
    ser.rts = opts.rts
    ser.dtr = opts.dtr
    ser.open()
    return ser


class CatConnection:
    """Thread-safe request/response wrapper around a transport."""

    def __init__(
        self,
        transport: Transport,
        *,
        timeout: float = 1.0,
        trace: Optional[TraceFn] = None,
        post_set_delay: float = 0.03,
    ):
        self._t = transport
        self._rx = bytearray()
        self._lock = threading.RLock()
        self.timeout = timeout
        self.trace = trace
        self.post_set_delay = post_set_delay

    # ------------------------------------------------------------------ basics
    @property
    def transport(self) -> Transport:
        return self._t

    @property
    def baudrate(self) -> int:
        return self._t.baudrate

    def change_baudrate(self, baud: int) -> None:
        with self._lock:
            self._t.baudrate = baud
            self._drain()

    def close(self) -> None:
        with self._lock:
            try:
                self._t.close()
            except Exception:
                pass

    def _trace(self, direction: str, text: str) -> None:
        if self.trace is not None:
            try:
                self.trace(direction, text)
            except Exception:
                pass

    def _drain(self) -> None:
        """Throw away anything unsolicited (e.g. auto-information) still buffered."""
        self._rx.clear()
        try:
            self._t.reset_input_buffer()
        except Exception:
            pass

    def _send(self, cmd: str) -> None:
        if not cmd.endswith(";"):
            cmd += ";"
        self._trace("TX", cmd)
        self._t.write(cmd.encode("ascii"))

    def _read_answer(self, deadline: float, cmd: str) -> str:
        """Return the next ``;``-terminated answer (without the ``;``)."""
        while True:
            idx = self._rx.find(b";")
            if idx >= 0:
                raw = bytes(self._rx[:idx])
                del self._rx[: idx + 1]
                text = raw.decode("ascii", errors="replace").strip("\r\n\x00 ")
                self._trace("RX", text + ";")
                return text
            if time.monotonic() >= deadline:
                if self._rx:
                    self._trace("RX", "(partial) " + self._rx.decode("ascii", errors="replace"))
                raise CatTimeout(cmd)
            waiting = 0
            try:
                waiting = self._t.in_waiting
            except Exception:
                pass
            chunk = self._t.read(waiting or 1)
            if chunk:
                self._rx += chunk

    # ---------------------------------------------------------------- commands
    def set(self, cmd: str) -> None:
        """Send a set command; no answer is expected."""
        with self._lock:
            self._send(cmd)
            if self.post_set_delay:
                time.sleep(self.post_set_delay)

    def query(self, cmd: str, prefix: Optional[str] = None, timeout: Optional[float] = None) -> str:
        """Send a read command and return the answer that starts with ``prefix``.

        Raises :class:`CatRejected` if the radio answers ``?;`` and
        :class:`CatTimeout` if nothing matching arrives in time.
        """
        prefix = (prefix or cmd[:2]).upper()
        with self._lock:
            self._drain()
            self._send(cmd)
            deadline = time.monotonic() + (self.timeout if timeout is None else timeout)
            while True:
                ans = self._read_answer(deadline, cmd)
                if ans == "?":
                    raise CatRejected(cmd)
                if ans.upper().startswith(prefix):
                    return ans
                # Anything else is unsolicited auto-information; ignore it.

    def set_and_read(
        self,
        set_cmd: str,
        read_cmd: str,
        prefix: Optional[str] = None,
        settle: Optional[float] = None,
    ) -> tuple[str, bool]:
        """Send ``set_cmd`` followed by ``read_cmd`` and return the read answer.

        Returns ``(answer, rejected)`` where ``rejected`` is True if the radio
        answered ``?;`` to the set command.  The caller should compare the
        answer with what it tried to write.
        """
        prefix = (prefix or read_cmd[:2]).upper()
        with self._lock:
            self._drain()
            self._send(set_cmd)
            delay = self.post_set_delay if settle is None else settle
            if delay:
                time.sleep(delay)
            self._send(read_cmd)
            deadline = time.monotonic() + self.timeout
            rejections = 0
            while True:
                try:
                    ans = self._read_answer(deadline, read_cmd)
                except CatTimeout:
                    if rejections:
                        raise CatRejected(set_cmd) from None
                    raise
                if ans == "?":
                    rejections += 1
                    if rejections >= 2:  # both the set and the read were rejected
                        raise CatRejected(set_cmd)
                    continue
                if ans.upper().startswith(prefix):
                    return ans, rejections > 0


def connect(opts: SerialOptions, trace: Optional[TraceFn] = None) -> CatConnection:
    """Open the port described by ``opts`` (or the built-in simulator)."""
    if opts.port.upper() == SIMULATOR_PORT:
        from .simulator import SimulatedRadio

        transport: Transport = SimulatedRadio(baudrate=opts.baudrate)
    else:
        transport = open_serial(opts)
    return CatConnection(transport, timeout=opts.timeout, trace=trace)


def probe_baud(opts: SerialOptions, trace: Optional[TraceFn] = None) -> Optional[tuple[int, str]]:
    """Try each CAT baud rate and return ``(baud, radio_id)`` for the first that answers ``ID;``."""
    order = [opts.baudrate] + [b for b in BAUD_RATES if b != opts.baudrate]
    for baud in order:
        trial = SerialOptions(opts.port, baud, opts.stopbits, opts.rts, opts.dtr, timeout=0.6)
        cat = connect(trial, trace)  # let "port busy / not found" errors propagate
        try:
            # Two attempts: a previous wrong-baud attempt can leave garbage that
            # the radio answers with "?;".
            for _ in range(2):
                try:
                    ans = cat.query("ID;", "ID")
                    return baud, ans[2:]
                except CatRejected:
                    time.sleep(0.05)
                except CatTimeout:
                    break
        finally:
            cat.close()
    return None
