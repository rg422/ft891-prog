"""FT-891 memory channels: data model and MR / MW / MT encoding.

Answer / command layout (0-based character positions, CAT Reference Book p.12-13)::

    0-1   "MR" / "MW" / "MT"
    2-4   P1  channel: 001-099, P1L-P9U (PMS), 501-510 (5 MHz, read only), EMG
    5-13  P2  frequency in Hz, 9 digits
    14    P3  clarifier direction "+" / "-"
    15-18 P3  clarifier offset 0000-9999 Hz
    19    P4  clarifier 0=OFF 1=ON
    20    P5  0 (fixed)
    21    P6  mode
    22    P7  0=VFO 1=Memory (MR answer) / 0 fixed (MW, MT)
    23    P8  CTCSS 0=OFF 1=ENC/DEC 2=ENC
    24-25 P9  00 (fixed)
    26    P10 repeater shift 0=simplex 1=plus 2=minus
    MT only:
    27    P11 tag display 0=OFF (show frequency) 1=ON (show tag)
    28-39 P12 tag, 12 ASCII characters (space padded)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Optional

# Mode codes (P6) and the names the FT-891 shows on its display.
MODE_CODES: dict[str, str] = {
    "1": "LSB",
    "2": "USB",
    "3": "CW-U",
    "4": "FM",
    "5": "AM",
    "6": "RTTY-L",
    "7": "CW-L",
    "8": "DATA-L",
    "9": "RTTY-U",
    "B": "FM-N",
    "C": "DATA-U",
    "D": "AM-N",
}
MODE_TO_CODE: dict[str, str] = {name: code for code, name in MODE_CODES.items()}
MODES: tuple[str, ...] = ("LSB", "USB", "CW-U", "CW-L", "AM", "AM-N", "FM", "FM-N",
                          "RTTY-L", "RTTY-U", "DATA-L", "DATA-U")

CTCSS_CODES: dict[str, str] = {"0": "OFF", "1": "ENC/DEC", "2": "ENC"}
CTCSS_TO_CODE = {v: k for k, v in CTCSS_CODES.items()}
SHIFT_CODES: dict[str, str] = {"0": "SIMPLEX", "1": "PLUS", "2": "MINUS"}
SHIFT_TO_CODE = {v: k for k, v in SHIFT_CODES.items()}

REGULAR_CHANNELS: tuple[str, ...] = tuple(f"{n:03d}" for n in range(1, 100))
PMS_CHANNELS: tuple[str, ...] = tuple(f"P{n}{side}" for n in range(1, 10) for side in "LU")
FIVE_MHZ_CHANNELS: tuple[str, ...] = tuple(f"5{n:02d}" for n in range(1, 11))
EMERGENCY_CHANNEL = "EMG"
WRITABLE_CHANNELS: tuple[str, ...] = REGULAR_CHANNELS + PMS_CHANNELS
READONLY_CHANNELS: tuple[str, ...] = FIVE_MHZ_CHANNELS + (EMERGENCY_CHANNEL,)
ALL_CHANNELS: tuple[str, ...] = WRITABLE_CHANNELS + READONLY_CHANNELS

FREQ_MIN_HZ = 30_000
FREQ_MAX_HZ = 56_000_000
TAG_LENGTH = 12
CLAR_MAX_HZ = 9999


def channel_label(ch: str) -> str:
    """Human-friendly channel name (``001`` -> ``01``, ``501`` -> ``5-01``)."""
    if ch in REGULAR_CHANNELS:
        return ch[1:]
    if ch in FIVE_MHZ_CHANNELS:
        return f"5-{ch[1:]}"
    return ch


def channel_from_label(text: str) -> str:
    """Inverse of :func:`channel_label`; also accepts CAT style names."""
    t = text.strip().upper()
    if t.isdigit():
        n = int(t)
        if 1 <= n <= 99:
            return f"{n:03d}"
        if 501 <= n <= 510:
            return str(n)
    if t.startswith("5-") and t[2:].isdigit():
        return f"5{int(t[2:]):02d}"
    if t in PMS_CHANNELS or t == EMERGENCY_CHANNEL:
        return t
    raise ValueError(f"unknown memory channel {text!r}")


def is_writable(ch: str) -> bool:
    return ch in WRITABLE_CHANNELS


def valid_tag_char(c: str) -> bool:
    return " " <= c <= "~" and c != ";"


@dataclass(frozen=True)
class MemoryChannel:
    channel: str
    freq_hz: int
    mode: str = "USB"
    clar_on: bool = False
    clar_offset_hz: int = 0
    ctcss: str = "OFF"
    shift: str = "SIMPLEX"
    tag: str = ""
    tag_on: bool = False

    # ------------------------------------------------------------- helpers
    def with_channel(self, ch: str) -> "MemoryChannel":
        return replace(self, channel=ch)

    def validate(self) -> list[str]:
        """Return a list of problems (empty when the channel can be written)."""
        errors = []
        if not (FREQ_MIN_HZ <= self.freq_hz <= FREQ_MAX_HZ):
            errors.append(f"frequency {format_freq(self.freq_hz)} MHz outside 0.030-56.000 MHz")
        if self.mode not in MODE_TO_CODE:
            errors.append(f"unknown mode {self.mode!r}")
        if abs(self.clar_offset_hz) > CLAR_MAX_HZ:
            errors.append("clarifier offset must be within +/-9999 Hz")
        if self.ctcss not in CTCSS_TO_CODE:
            errors.append(f"unknown CTCSS setting {self.ctcss!r}")
        if self.shift not in SHIFT_TO_CODE:
            errors.append(f"unknown repeater shift {self.shift!r}")
        if len(self.tag) > TAG_LENGTH:
            errors.append(f"tag longer than {TAG_LENGTH} characters")
        bad = sorted({c for c in self.tag if not valid_tag_char(c)})
        if bad:
            errors.append(f"tag contains unsupported characters: {''.join(bad)!r}")
        return errors

    def same_radio_data(self, other: "MemoryChannel", compare_tag: bool = True) -> bool:
        """Compare everything the radio stores (ignoring the channel number)."""
        a = replace(self, channel="")
        b = replace(other, channel="")
        if not compare_tag:
            a = replace(a, tag="", tag_on=False)
            b = replace(b, tag="", tag_on=False)
        else:
            a = replace(a, tag=a.tag.rstrip())
            b = replace(b, tag=b.tag.rstrip())
        return a == b

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryChannel":
        mem = cls(
            channel=str(data["channel"]),
            freq_hz=int(data["freq_hz"]),
            mode=str(data.get("mode", "USB")),
            clar_on=bool(data.get("clar_on", False)),
            clar_offset_hz=int(data.get("clar_offset_hz", 0)),
            ctcss=str(data.get("ctcss", "OFF")),
            shift=str(data.get("shift", "SIMPLEX")),
            tag=str(data.get("tag", "")),
            tag_on=bool(data.get("tag_on", False)),
        )
        errors = mem.validate()
        if errors:
            raise ValueError(f"channel {data.get('channel')}: " + "; ".join(errors))
        return mem


# ---------------------------------------------------------------------- parsing
def parse_memory_answer(answer: str) -> MemoryChannel:
    """Parse an ``MR``/``MT`` answer (with or without the trailing ``;``)."""
    ans = answer.rstrip(";")
    cmd = ans[:2].upper()
    if cmd not in ("MR", "MT", "MW") or len(ans) < 27:
        raise ValueError(f"unexpected memory answer {answer!r}")
    ch = ans[2:5].upper()
    try:
        freq = int(ans[5:14])
        sign = ans[14]
        offset = int(ans[15:19])
    except ValueError:
        raise ValueError(f"unexpected memory answer {answer!r}") from None
    if sign == "-":
        offset = -offset
    mode = MODE_CODES.get(ans[21].upper())
    if mode is None:
        raise ValueError(f"unknown mode code {ans[21]!r} in {answer!r}")
    tag = ""
    tag_on = False
    if cmd == "MT" and len(ans) >= 28:
        tag_on = ans[27] == "1"
        tag = ans[28:28 + TAG_LENGTH].rstrip()
    return MemoryChannel(
        channel=ch,
        freq_hz=freq,
        mode=mode,
        clar_on=ans[19] == "1",
        clar_offset_hz=offset,
        ctcss=CTCSS_CODES.get(ans[23], "OFF"),
        shift=SHIFT_CODES.get(ans[26], "SIMPLEX"),
        tag=tag,
        tag_on=tag_on,
    )


def _body(mem: MemoryChannel, p7: str) -> str:
    sign = "-" if mem.clar_offset_hz < 0 else "+"
    return (
        f"{mem.channel}"
        f"{mem.freq_hz:09d}"
        f"{sign}{abs(mem.clar_offset_hz):04d}"
        f"{'1' if mem.clar_on else '0'}"
        "0"
        f"{MODE_TO_CODE[mem.mode]}"
        f"{p7}"
        f"{CTCSS_TO_CODE[mem.ctcss]}"
        "00"
        f"{SHIFT_TO_CODE[mem.shift]}"
    )


def _check_writable(mem: MemoryChannel) -> None:
    if not is_writable(mem.channel):
        raise ValueError(f"channel {mem.channel} cannot be written via CAT")
    errors = mem.validate()
    if errors:
        raise ValueError(f"channel {channel_label(mem.channel)}: " + "; ".join(errors))


def format_mw(mem: MemoryChannel) -> str:
    """``MW`` set command (memory write without tag)."""
    _check_writable(mem)
    return f"MW{_body(mem, '0')};"


def format_mt(mem: MemoryChannel) -> str:
    """``MT`` set command (memory write including the 12-character tag)."""
    _check_writable(mem)
    tag = mem.tag[:TAG_LENGTH].ljust(TAG_LENGTH)
    return f"MT{_body(mem, '0')}{'1' if mem.tag_on else '0'}{tag};"


def format_answer(mem: MemoryChannel, cmd: str = "MR") -> str:
    """Build the answer the radio would send (used by the simulator and tests)."""
    if cmd == "MR":
        return f"MR{_body(mem, '1')};"
    tag = mem.tag[:TAG_LENGTH].ljust(TAG_LENGTH)
    return f"MT{_body(mem, '1')}{'1' if mem.tag_on else '0'}{tag};"


# ------------------------------------------------------------- frequency text
def format_freq(freq_hz: int) -> str:
    """14250000 -> ``14.250000`` (MHz)."""
    return f"{freq_hz // 1_000_000}.{freq_hz % 1_000_000:06d}"


def parse_freq(text: str) -> int:
    """Parse a user-entered frequency and return Hz.

    Accepts ``14.250``, ``14.250.000`` (radio style), ``14250 kHz``,
    ``14250000 Hz``.  A bare number without a decimal point is read as MHz
    if < 100, kHz if < 100 000, otherwise Hz.
    """
    t = text.strip().lower().replace(",", "").replace(" ", "")
    if not t:
        raise ValueError("frequency is empty")
    unit = None
    for suffix in ("mhz", "khz", "hz"):
        if t.endswith(suffix):
            unit = suffix
            t = t[: -len(suffix)]
            break
    if t.count(".") > 1:  # 14.250.000 style: first dot is the MHz separator
        head, _, rest = t.partition(".")
        t = head + "." + rest.replace(".", "")
        unit = unit or "mhz"
    try:
        value = float(t)
    except ValueError:
        raise ValueError(f"'{text}' is not a frequency") from None
    if unit is None:
        if "." in t or value < 100:
            unit = "mhz"
        elif value < 100_000:
            unit = "khz"
        else:
            unit = "hz"
    factor = {"mhz": 1_000_000, "khz": 1_000, "hz": 1}[unit]
    hz = int(round(value * factor))
    if not (FREQ_MIN_HZ <= hz <= FREQ_MAX_HZ):
        raise ValueError(f"{format_freq(hz)} MHz is outside the FT-891 range (0.030-56.000 MHz)")
    return hz


def default_mode_for(freq_hz: int) -> str:
    """Sensible default mode for a new channel."""
    if freq_hz < 1_800_000:
        return "AM"
    if 5_000_000 <= freq_hz < 5_500_000:  # 60 m channels are USB
        return "USB"
    if freq_hz < 10_000_000:
        return "LSB"
    if 29_500_000 <= freq_hz <= 29_700_000:
        return "FM"
    return "USB"
