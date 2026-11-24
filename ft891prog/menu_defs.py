"""FT-891 menu ("EX" command) definitions.

Source: Yaesu *FT-891 CAT Operation Reference Book* (EX command table) for the
CAT parameter encoding and the *FT-891 Advance Manual* menu table for defaults.

Every item stores its value as a *raw* integer - exactly the number that goes
into the EX command's P2 field.  ``display()`` turns a raw value into the text
shown on the radio, ``encode()`` produces the fixed-width P2 string.

Menu 17-01 (RESET) is deliberately not included: writing it would reset the
radio.  Menu 18-xx (firmware versions) is read-only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

GROUPS: dict[int, str] = {
    1: "AGC",
    2: "DISPLAY",
    3: "DVS",
    4: "KEYER",
    5: "GENERAL",
    6: "MODE AM",
    7: "MODE CW",
    8: "MODE DAT",
    9: "MODE FM",
    10: "MODE RTY",
    11: "MODE SSB",
    12: "RX DSP",
    13: "SCOPE",
    14: "TUNING",
    15: "TX AUDIO",
    16: "TX GNRL",
    18: "VERSION",
}


@dataclass(frozen=True)
class MenuItem:
    number: str                    # four digit CAT menu number, e.g. "0101"
    name: str                      # name as shown on the radio
    digits: int                    # width of the P2 field (sign included)
    kind: str                      # "enum" or "int"
    choices: tuple[tuple[int, str], ...] = ()
    minimum: int = 0
    maximum: int = 0
    step: int = 1
    signed: bool = False           # P2 carries an explicit +/- sign
    unit: str = ""
    scale: int = 1                 # displayed value = raw / scale
    special: tuple[tuple[int, str], ...] = ()   # labels for special raw values (e.g. 0 = OFF)
    allowed: Optional[tuple[int, ...]] = None   # explicit list of legal raw values
    default: Optional[int] = None
    readonly: bool = False
    note: str = ""
    range_hint: str = ""           # overrides the generated range description
    _choice_map: dict = field(default=None, compare=False, repr=False)  # type: ignore[assignment]

    def __post_init__(self):
        object.__setattr__(self, "_choice_map", dict(self.choices) if self.choices else {})

    # ----------------------------------------------------------- identity
    @property
    def group(self) -> int:
        return int(self.number[:2])

    @property
    def group_name(self) -> str:
        return GROUPS.get(self.group, "?")

    @property
    def label(self) -> str:
        """Menu number as printed on the radio, e.g. ``01-01``."""
        return f"{self.number[:2]}-{self.number[2:]}"

    # ------------------------------------------------------- validation
    def legal_values(self) -> list[int]:
        if self.kind == "enum":
            return [raw for raw, _ in self.choices]
        if self.allowed is not None:
            return list(self.allowed)
        return list(range(self.minimum, self.maximum + 1, self.step))

    def is_valid(self, raw: int) -> bool:
        if self.kind == "enum":
            return raw in self._choice_map
        if self.allowed is not None:
            return raw in self.allowed
        if raw in dict(self.special):
            return True
        return self.minimum <= raw <= self.maximum and (raw - self.minimum) % self.step == 0

    # --------------------------------------------------------- encoding
    def encode(self, raw: int, width: Optional[int] = None) -> str:
        """Format ``raw`` as the fixed-width P2 field."""
        width = width or self.digits
        if self.signed:
            sign = "-" if raw < 0 else "+"
            return f"{sign}{abs(raw):0{width - 1}d}"
        if raw < 0:
            raise ValueError(f"{self.label} {self.name}: negative value {raw} not allowed")
        text = f"{raw:0{width}d}"
        if len(text) > width:
            raise ValueError(f"{self.label} {self.name}: value {raw} does not fit in {width} digits")
        return text

    def decode(self, p2: str) -> int:
        """Parse a P2 field returned by the radio."""
        text = p2.strip()
        if not text or not (text.lstrip("+-").isdigit()):
            raise ValueError(f"{self.label} {self.name}: unexpected value {p2!r}")
        return int(text)

    # ---------------------------------------------------------- display
    def display(self, raw: Optional[int]) -> str:
        if raw is None:
            return ""
        if self.kind == "enum":
            return self._choice_map.get(raw, f"? ({raw})")
        special = dict(self.special)
        if raw in special:
            return special[raw]
        return f"{self._number_text(raw)} {self.unit}".strip()

    def _number_text(self, raw: int) -> str:
        if self.scale != 1:
            decimals = len(str(self.scale)) - 1
            text = f"{raw / self.scale:.{decimals}f}"
        else:
            text = str(raw)
        return "+" + text if self.signed and raw > 0 else text

    def range_text(self) -> str:
        if self.readonly:
            return "read only"
        if self.range_hint:
            return self.range_hint
        if self.kind == "enum":
            labels = [label for _, label in self.choices]
            if len(labels) > 6:
                return f"{labels[0]}, {labels[1]} ... {labels[-1]}"
            return " / ".join(labels)
        special = dict(self.special)
        lo = self.minimum + (self.step if self.minimum in special else 0)
        rng = f"{self._number_text(lo)} to {self._number_text(self.maximum)}"
        if self.unit:
            rng += f" {self.unit}"
        if self.step != 1:
            rng += f", step {self.step / self.scale:g}"
        return ", ".join([*special.values(), rng])

    def options(self) -> list[str]:
        """Display strings for every legal value (used for drop-down editors)."""
        return [self.display(v) for v in self.legal_values()]

    def parse_display(self, text: str) -> int:
        """Convert user-entered text (a display label or a number) to a raw value."""
        t = text.strip()
        if not t:
            raise ValueError("empty value")
        if self.kind == "enum":
            for raw, label in self.choices:
                if label.lower() == t.lower():
                    return raw
            raise ValueError(f"'{text}' is not one of: {', '.join(l for _, l in self.choices)}")
        for raw, label in self.special:
            if label.lower() == t.lower():
                return raw
        num_txt = t
        if self.unit and num_txt.lower().endswith(self.unit.lower()):
            num_txt = num_txt[: -len(self.unit)].strip()
        try:
            value = float(num_txt)
        except ValueError:
            raise ValueError(f"'{text}' is not a number") from None
        raw = int(round(value * self.scale))
        if not self.is_valid(raw):
            raise ValueError(f"{self.display(raw)} is out of range ({self.range_text()})")
        return raw


# --------------------------------------------------------------------- helpers
def _enum(number: str, name: str, labels, default: Optional[int], digits: int = 1,
          start: int = 0, note: str = "") -> MenuItem:
    if isinstance(labels, dict):
        choices = tuple(labels.items())
    else:
        choices = tuple((start + i, label) for i, label in enumerate(labels))
    return MenuItem(number, name, digits, "enum", choices=choices, default=default, note=note)


def _int(number: str, name: str, lo: int, hi: int, default: Optional[int], digits: int, *,
         step: int = 1, unit: str = "", scale: int = 1, signed: bool = False,
         special: Optional[dict] = None, allowed=None, readonly: bool = False,
         note: str = "", range_hint: str = "") -> MenuItem:
    return MenuItem(number, name, digits, "int", minimum=lo, maximum=hi, step=step,
                    signed=signed, unit=unit, scale=scale,
                    special=tuple((special or {}).items()),
                    allowed=tuple(allowed) if allowed is not None else None,
                    default=default, readonly=readonly, note=note, range_hint=range_hint)


def _onoff(number: str, name: str, default: int, note: str = "") -> MenuItem:
    return _enum(number, name, ["DISABLE", "ENABLE"], default, note=note)


_LCUT = {0: "OFF", **{n: f"{50 + 50 * n} Hz" for n in range(1, 20)}}       # 100-1000 Hz
_HCUT = {0: "OFF", **{n: f"{650 + 50 * n} Hz" for n in range(1, 68)}}      # 700-4000 Hz
_SLOPE = ["6 dB/oct", "18 dB/oct"]
_PTT = ["DAKY", "RTS", "DTR"]
_MICSEL = ["MIC", "REAR"]
_EQ1 = {0: "OFF", **{n: f"{100 * n} Hz" for n in range(1, 8)}}             # 100-700 Hz
_EQ2 = {0: "OFF", **{n: f"{600 + 100 * n} Hz" for n in range(1, 10)}}      # 700-1500 Hz
_EQ3 = {0: "OFF", **{n: f"{1400 + 100 * n} Hz" for n in range(1, 19)}}     # 1500-3200 Hz
_BEACON = (0, *range(1, 241), *range(270, 691, 30))


def _level(number: str, name: str, default: int = 50) -> MenuItem:
    return _int(number, name, 0, 100, default, 3)


def _eq_level(number: str, name: str, default: int) -> MenuItem:
    return _int(number, name, -20, 10, default, 3, signed=True, unit="dB")


def _eq_bw(number: str, name: str, default: int) -> MenuItem:
    return _int(number, name, 1, 10, default, 2)


MENU_ITEMS: tuple[MenuItem, ...] = (
    # 01 AGC
    _int("0101", "AGC FAST DELAY", 20, 4000, 300, 4, step=20, unit="msec"),
    _int("0102", "AGC MID DELAY", 20, 4000, 700, 4, step=20, unit="msec"),
    _int("0103", "AGC SLOW DELAY", 20, 4000, 3000, 4, step=20, unit="msec"),
    # 02 DISPLAY
    _int("0201", "LCD CONTRAST", 1, 15, 8, 2),
    _int("0202", "DIMMER BACKLIT", 1, 15, 8, 2),
    _int("0203", "DIMMER LCD", 1, 15, 8, 2),
    _int("0204", "DIMMER TX/BUSY", 1, 15, 8, 2),
    _enum("0205", "PEAK HOLD", ["OFF", "0.5 sec", "1.0 sec", "2.0 sec"], 0),
    _onoff("0206", "ZIN LED", 0),
    _enum("0207", "POP-UP MENU", ["UPPER", "LOWER"], 1),
    # 03 DVS
    _level("0301", "DVS RX OUT LVL"),
    _level("0302", "DVS TX OUT LVL"),
    # 04 KEYER
    _enum("0401", "KEYER TYPE", ["OFF", "BUG", "ELEKEY-A", "ELEKEY-B", "ELEKEY-Y", "ACS"], 3),
    _enum("0402", "KEYER DOT/DASH", ["NOR", "REV"], 0),
    _int("0403", "CW WEIGHT", 25, 45, 30, 2, scale=10),
    _int("0404", "BEACON INTERVAL", 0, 690, 0, 3, unit="sec", special={0: "OFF"}, allowed=_BEACON,
         range_hint="OFF, 1 to 240 sec (1 s steps), 270 to 690 sec (30 s steps)"),
    _enum("0405", "NUMBER STYLE", ["1290", "AUNO", "AUNT", "A2NO", "A2NT", "12NO", "12NT"], 0),
    _int("0406", "CONTEST NUMBER", 0, 9999, 1, 4),
    _enum("0407", "CW MEMORY 1", ["TEXT", "MESSAGE"], 0),
    _enum("0408", "CW MEMORY 2", ["TEXT", "MESSAGE"], 0),
    _enum("0409", "CW MEMORY 3", ["TEXT", "MESSAGE"], 0),
    _enum("0410", "CW MEMORY 4", ["TEXT", "MESSAGE"], 0),
    _enum("0411", "CW MEMORY 5", ["TEXT", "MESSAGE"], 0),
    # 05 GENERAL
    _enum("0501", "NB WIDTH", ["1 msec", "3 msec", "10 msec"], 1),
    _enum("0502", "NB REJECTION", ["10 dB", "30 dB", "50 dB"], 1),
    _int("0503", "NB LEVEL", 0, 10, 5, 2),
    _int("0504", "BEEP LEVEL", 0, 100, 30, 3),
    _enum("0505", "RF/SQL VR", ["RF", "SQL"], 0),
    _enum("0506", "CAT RATE", ["4800 bps", "9600 bps", "19200 bps", "38400 bps"], 0,
          note="Changes the radio's CAT baud rate. The program writes this item last "
               "and then reconnects at the new rate."),
    _enum("0507", "CAT TOT", ["10 msec", "100 msec", "1000 msec", "3000 msec"], 0),
    _onoff("0508", "CAT RTS", 1, note="When ENABLE the radio monitors the RTS line of the CAT port."),
    _onoff("0509", "MEM GROUP", 0),
    _onoff("0510", "FM SETTING", 0),
    _onoff("0511", "REC SETTING", 0),
    _onoff("0512", "ATAS SETTING", 0),
    _int("0513", "QUICK SPL FREQ", -20, 20, 5, 3, signed=True, unit="kHz"),
    _int("0514", "TX TOT", 0, 30, 0, 2, unit="min", special={0: "OFF"}),
    _onoff("0515", "MIC SCAN", 1),
    _enum("0516", "MIC SCAN RESUME", ["PAUSE", "TIME"], 1),
    _int("0517", "REF FREQ ADJ", -25, 25, 0, 3, signed=True,
         note="Reference oscillator trim. Only change this if you know your radio's calibration."),
    _enum("0518", "CLAR SELECT", ["RX", "TX", "TRX"], 0),
    _enum("0519", "APO", ["OFF", "1 h", "2 h", "4 h", "6 h", "8 h", "10 h", "12 h"], 0),
    _enum("0520", "FAN CONTROL", ["NORMAL", "CONTEST"], 0),
    # 06 MODE AM
    _enum("0601", "AM LCUT FREQ", _LCUT, 0, digits=2),
    _enum("0602", "AM LCUT SLOPE", _SLOPE, 0),
    _enum("0603", "AM HCUT FREQ", _HCUT, 0, digits=2),
    _enum("0604", "AM HCUT SLOPE", _SLOPE, 0),
    _enum("0605", "AM MIC SELECT", _MICSEL, 0),
    _level("0606", "AM OUT LEVEL"),
    _enum("0607", "AM PTT SELECT", _PTT, 0),
    # 07 MODE CW
    _enum("0701", "CW LCUT FREQ", _LCUT, 4, digits=2),
    _enum("0702", "CW LCUT SLOPE", _SLOPE, 1),
    _enum("0703", "CW HCUT FREQ", _HCUT, 11, digits=2),
    _enum("0704", "CW HCUT SLOPE", _SLOPE, 1),
    _level("0705", "CW OUT LEVEL"),
    _enum("0706", "CW AUTO MODE", ["OFF", "50M", "ON"], 0),
    _enum("0707", "CW BFO", ["USB", "LSB", "AUTO"], 0),
    _enum("0708", "CW BK-IN TYPE", ["SEMI", "FULL"], 0),
    _int("0709", "CW BK-IN DELAY", 30, 3000, 200, 4, step=10, unit="msec"),
    _enum("0710", "CW WAVE SHAPE", {1: "2 msec", 2: "4 msec"}, 2),
    _enum("0711", "CW FREQ DISPLAY", ["FREQ", "PITCH"], 1),
    _enum("0712", "PC KEYING", ["OFF", "DAKY", "RTS", "DTR"], 0),
    _enum("0713", "QSK DELAY TIME", ["15 msec", "20 msec", "25 msec", "30 msec"], 0),
    # 08 MODE DAT
    _enum("0801", "DATA MODE", ["PSK", "OTHERS"], 0),
    _enum("0802", "PSK TONE", ["1000 Hz", "1500 Hz", "2000 Hz"], 0),
    _int("0803", "OTHER DISP", -3000, 3000, 0, 5, step=10, signed=True, unit="Hz"),
    _int("0804", "OTHER SHIFT", -3000, 3000, 0, 5, step=10, signed=True, unit="Hz"),
    _enum("0805", "DATA LCUT FREQ", _LCUT, 5, digits=2),
    _enum("0806", "DATA LCUT SLOPE", _SLOPE, 1),
    _enum("0807", "DATA HCUT FREQ", _HCUT, 47, digits=2),
    _enum("0808", "DATA HCUT SLOPE", _SLOPE, 1),
    _enum("0809", "DATA IN SELECT", _MICSEL, 1),
    _enum("0810", "DATA PTT SELECT", _PTT, 0),
    _level("0811", "DATA OUT LEVEL"),
    _enum("0812", "DATA BFO", ["USB", "LSB"], 1),
    # 09 MODE FM
    _enum("0901", "FM MIC SELECT", _MICSEL, 0),
    _level("0902", "FM OUT LEVEL"),
    _enum("0903", "PKT PTT SELECT", _PTT, 0),
    _int("0904", "RPT SHIFT 28MHz", 0, 1000, 100, 4, step=10, unit="kHz"),
    # The CAT manual lists 1 digit for 09-05 but its range (0000-4000) needs 4.
    _int("0905", "RPT SHIFT 50MHz", 0, 4000, 1000, 4, step=10, unit="kHz"),
    _enum("0906", "DCS POLARITY", ["Tn-Rn", "Tn-Riv", "Tiv-Rn", "Tiv-Riv"], 0),
    # 10 MODE RTY
    _enum("1001", "RTTY LCUT FREQ", _LCUT, 5, digits=2),
    _enum("1002", "RTTY LCUT SLOPE", _SLOPE, 1),
    _enum("1003", "RTTY HCUT FREQ", _HCUT, 47, digits=2),
    _enum("1004", "RTTY HCUT SLOPE", _SLOPE, 1),
    _enum("1005", "RTTY SHIFT PORT", ["SHIFT", "DTR", "RTS"], 0),
    _enum("1006", "RTTY POLARITY-R", ["NOR", "REV"], 0),
    _enum("1007", "RTTY POLARITY-T", ["NOR", "REV"], 0),
    _level("1008", "RTTY OUT LEVEL"),
    _enum("1009", "RTTY SHIFT FREQ", ["170 Hz", "200 Hz", "425 Hz", "850 Hz"], 0),
    _enum("1010", "RTTY MARK FREQ", ["1275 Hz", "2125 Hz"], 1),
    _enum("1011", "RTTY BFO", ["USB", "LSB"], 1),
    # 11 MODE SSB
    _enum("1101", "SSB LCUT FREQ", _LCUT, 1, digits=2),
    _enum("1102", "SSB LCUT SLOPE", _SLOPE, 0),
    _enum("1103", "SSB HCUT FREQ", _HCUT, 47, digits=2),
    _enum("1104", "SSB HCUT SLOPE", _SLOPE, 0),
    _enum("1105", "SSB MIC SELECT", _MICSEL, 0),
    _level("1106", "SSB OUT LEVEL"),
    _enum("1107", "SSB BFO", ["USB", "LSB", "AUTO"], 2),
    _enum("1108", "SSB PTT SELECT", _PTT, 0),
    _enum("1109", "SSB TX BPF", ["100-3000", "100-2900", "200-2800", "300-2700", "400-2600"], 3),
    # 12 RX DSP
    _enum("1201", "APF WIDTH", ["NARROW", "MEDIUM", "WIDE"], 1),
    _int("1202", "CONTOUR LEVEL", -40, 20, -15, 3, signed=True),
    _int("1203", "CONTOUR WIDTH", 1, 11, 10, 2),
    _enum("1204", "IF NOTCH WIDTH", ["NARROW", "WIDE"], 1),
    # 13 SCOPE
    _enum("1301", "SCP START CYCLE", ["OFF", "3 sec", "5 sec", "10 sec"], 0),
    _enum("1302", "SCP SPAN FREQ", ["37.5 kHz", "75 kHz", "150 kHz", "375 kHz", "750 kHz"], 4),
    # 14 TUNING
    _enum("1401", "QUICK DIAL", ["50 kHz", "100 kHz", "500 kHz"], 2),
    _enum("1402", "SSB DIAL STEP", ["2 Hz", "5 Hz", "10 Hz"], 2),
    _enum("1403", "AM DIAL STEP", ["10 Hz", "100 Hz"], 0),
    _enum("1404", "FM DIAL STEP", ["10 Hz", "100 Hz"], 1),
    _enum("1405", "DIAL STEP", ["2 Hz", "5 Hz", "10 Hz"], 1),
    _enum("1406", "AM CH STEP", ["2.5 kHz", "5 kHz", "9 kHz", "10 kHz", "12.5 kHz", "25 kHz"], 1),
    _enum("1407", "FM CH STEP", ["5 kHz", "6.25 kHz", "10 kHz", "12.5 kHz", "15 kHz", "20 kHz", "25 kHz"], 0),
    # 15 TX AUDIO (EQ = processor off, P-EQ = processor on)
    _enum("1501", "EQ1 FREQ", _EQ1, 0, digits=2),
    _eq_level("1502", "EQ1 LEVEL", 5),
    _eq_bw("1503", "EQ1 BWTH", 10),
    _enum("1504", "EQ2 FREQ", _EQ2, 0, digits=2),
    _eq_level("1505", "EQ2 LEVEL", 5),
    _eq_bw("1506", "EQ2 BWTH", 10),
    _enum("1507", "EQ3 FREQ", _EQ3, 0, digits=2),
    _eq_level("1508", "EQ3 LEVEL", 5),
    _eq_bw("1509", "EQ3 BWTH", 10),
    _enum("1510", "P-EQ1 FREQ", _EQ1, 2, digits=2),
    _eq_level("1511", "P-EQ1 LEVEL", 0),
    _eq_bw("1512", "P-EQ1 BWTH", 2),
    _enum("1513", "P-EQ2 FREQ", _EQ2, 2, digits=2),
    _eq_level("1514", "P-EQ2 LEVEL", 0),
    _eq_bw("1515", "P-EQ2 BWTH", 1),
    _enum("1516", "P-EQ3 FREQ", _EQ3, 7, digits=2),
    _eq_level("1517", "P-EQ3 LEVEL", 0),
    _eq_bw("1518", "P-EQ3 BWTH", 1),
    # 16 TX GNRL
    _int("1601", "HF SSB PWR", 5, 100, 100, 3, unit="W"),
    _int("1602", "HF AM PWR", 5, 40, 25, 3, unit="W"),
    _int("1603", "HF PWR", 5, 100, 100, 3, unit="W"),
    _int("1604", "50M SSB PWR", 5, 100, 100, 3, unit="W"),
    _int("1605", "50M AM PWR", 5, 40, 25, 3, unit="W"),
    _int("1606", "50M PWR", 5, 100, 100, 3, unit="W"),
    _level("1607", "SSB MIC GAIN"),
    _level("1608", "AM MIC GAIN"),
    _level("1609", "FM MIC GAIN"),
    _level("1610", "DATA MIC GAIN"),
    _level("1611", "SSB DATA GAIN"),
    _level("1612", "AM DATA GAIN"),
    _level("1613", "FM DATA GAIN"),
    _level("1614", "DATA DATA GAIN"),
    _enum("1615", "TUNER SELECT", ["OFF", "EXTERNAL", "ATAS", "LAMP"], 0),
    _enum("1616", "VOX SELECT", ["MIC", "DATA"], 0),
    _level("1617", "VOX GAIN"),
    _int("1618", "VOX DELAY", 30, 3000, 500, 4, step=10, unit="msec"),
    _level("1619", "ANTI VOX GAIN"),
    _level("1620", "DATA VOX GAIN"),
    _int("1621", "DATA VOX DELAY", 30, 3000, 100, 4, step=10, unit="msec"),
    _level("1622", "ANTI DVOX GAIN", 0),
    _onoff("1623", "EMERGENCY FREQ", 0,
           note="Enables TX on the Alaska emergency frequency (5167.5 kHz). US version only."),
    # 18 VERSION (read only)
    _int("1801", "MAIN VERSION", 0, 9999, None, 4, readonly=True),
    _int("1802", "DSP VERSION", 0, 9999, None, 4, readonly=True),
    _int("1803", "LCD VERSION", 0, 9999, None, 4, readonly=True),
)

MENU_BY_NUMBER: dict[str, MenuItem] = {item.number: item for item in MENU_ITEMS}
WRITABLE_ITEMS: tuple[MenuItem, ...] = tuple(i for i in MENU_ITEMS if not i.readonly)
VERSION_ITEMS: tuple[MenuItem, ...] = tuple(i for i in MENU_ITEMS if i.group == 18)
CAT_RATE = "0506"


def format_version(raw: Optional[int]) -> str:
    """18-0x answers encode V01-23 as 0123."""
    if raw is None:
        return "?"
    return f"V{raw // 100:02d}-{raw % 100:02d}"
