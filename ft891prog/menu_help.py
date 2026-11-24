"""Plain-language help for every FT-891 menu item.

Written for this program from the FT-891 Advance Manual (Menu Mode chapter and
the feature chapters it refers to).  Each entry explains what the setting
does and when you would change it.
"""

from __future__ import annotations


def _lcut(mode: str, extra: str = "") -> str:
    return (f"Low-cut audio filter for {mode} receive. Removes audio below the chosen frequency "
            f"(100-1000 Hz in 50 Hz steps), which cuts rumble and low-pitched noise. OFF leaves the "
            f"low end untouched. {extra}").strip()


def _hcut(mode: str, extra: str = "") -> str:
    return (f"High-cut audio filter for {mode} receive. Removes audio above the chosen frequency "
            f"(700-4000 Hz in 50 Hz steps) to reduce hiss and splatter. OFF leaves the top end "
            f"untouched. {extra}").strip()


def _slope(which: str, mode: str, item: str) -> str:
    return (f"How sharply the {which} filter in menu {item} rolls off in {mode} receive. "
            "6 dB/oct is a gentle, natural-sounding slope; 18 dB/oct is steeper and rejects more "
            "of the unwanted audio.")


def _mic_select(mode: str, gain_item: str) -> str:
    return (f"Audio source for {mode} transmit. MIC uses the front-panel microphone jack. REAR "
            "turns off the front microphone and takes audio from the rear RTTY/DATA jack, for "
            f"example from a computer interface. With REAR, the input level is set in menu "
            f"{gain_item}.")


def _out_level(mode: str) -> str:
    return (f"Level of the received {mode} audio sent out of the rear RTTY/DATA jack (to a "
            "computer sound card or other device). Higher is louder. It does not change the "
            "speaker volume.")


def _ptt(mode: str) -> str:
    return (f"What keys the transmitter for {mode} signals coming from the rear jack or a "
            "computer. DAKY = the DATA PTT pin (pin 3) of the rear RTTY/DATA jack. RTS or DTR = "
            "that control line of the radio's USB virtual COM port, so software can key the radio "
            "over the USB cable.")


def _bfo(mode: str, auto: bool) -> str:
    text = (f"Which sideband the carrier oscillator is injected on in {mode} mode. USB or LSB "
            "forces that side on every band.")
    if auto:
        text += " AUTO uses LSB on 7 MHz and below and USB on 10 MHz and above, following the usual convention."
    return text


def _eq(band: str, rng: str, part: str, processor: bool) -> str:
    when = ("Used only while the speech processor is ON (a separate EQ set, so you can tune "
            "processed audio differently)." if processor else
            "Used while the speech processor is OFF (menus 15-10 to 15-18 apply when it is ON).")
    if part == "freq":
        return (f"Centre frequency of the {band} band of the 3-band parametric microphone "
                f"equaliser ({rng}). OFF disables this band. {when}")
    if part == "level":
        return (f"Boost or cut for the {band} band of the microphone equaliser, from -20 dB to "
                f"+10 dB. Positive values emphasise that part of your voice. {when}")
    return (f"Width (Q) of the {band} equaliser band, 1 to 10. Low numbers affect a narrow range "
            f"around the centre frequency; high numbers affect a broad range. {when}")


def _data_gain(mode: str, select_item: str) -> str:
    return (f"Input level of audio from the rear RTTY/DATA jack when transmitting {mode} with "
            f"menu {select_item} set to REAR. Raise it if transmit audio from your interface is "
            "too weak; lower it if it overdrives (watch ALC).")


MENU_HELP: dict[str, str] = {
    # ---------------------------------------------------------------- 01 AGC
    "0101": ("How quickly the receiver gain recovers after a strong signal goes away when AGC "
             "is set to FAST (20-4000 ms, 20 ms steps). Shorter gives a snappier receiver for CW "
             "and fast-changing signals."),
    "0102": ("AGC recovery (decay) time when AGC is set to MID (20-4000 ms, 20 ms steps). A "
             "middle ground suited to general SSB listening."),
    "0103": ("AGC recovery (decay) time when AGC is set to SLOW (20-4000 ms, 20 ms steps). "
             "Longer times keep the background noise from pumping up between words on SSB and AM."),

    # ------------------------------------------------------------ 02 DISPLAY
    "0201": "Contrast of the LCD (1-15). Adjust for the clearest characters at your viewing angle.",
    "0202": "Brightness of the key backlighting LEDs (1-15). Higher is brighter.",
    "0203": "Brightness of the LCD backlight (1-15). Lower it for night-time or low-power operation.",
    "0204": "Brightness of the TX/BUSY indicator LED (1-15). Higher is brighter.",
    "0205": ("Meter peak hold: keeps the highest meter reading on screen for 0.5, 1 or 2 seconds "
             "so short peaks (for example ALC or power on voice) are easier to read. OFF shows the "
             "live reading only."),
    "0206": ("Uses the TX/BUSY indicator as a CW zero-in (tuning) indicator, helping you tune "
             "exactly onto a received CW station."),
    "0207": ("Where pop-up windows (such as level and frequency adjustments) appear on the "
             "display: UPPER or LOWER part of the screen."),

    # ---------------------------------------------------------------- 03 DVS
    "0301": ("Playback volume when you monitor messages stored in the voice memory (DVS). "
             "Higher is louder."),
    "0302": ("Transmit level of messages sent from the voice memory (DVS). Set it so recorded "
             "messages modulate the transmitter about as strongly as your live microphone."),

    # -------------------------------------------------------------- 04 KEYER
    "0401": ("Behaviour of the built-in electronic keyer. OFF = keyer disabled (straight key). "
             "BUG = automatic dots, manual dashes. ELEKEY-A / ELEKEY-B = iambic modes A and B "
             "(B adds an extra opposite element when you release a squeezed paddle). ELEKEY-Y = "
             "like B, but a dot pressed during a dash is not remembered. ACS = automatic character "
             "spacing: the keyer enforces a standard dash-length gap between letters."),
    "0402": ("Swaps the paddle sides. NOR = right paddle sends dots, left sends dashes. REV = the "
             "opposite, handy for left-handed operators, without rewiring the key."),
    "0403": ("Keyer weighting: the dash-to-dot length ratio (2.5 to 4.5, standard is 3.0). Higher "
             "values make heavier-sounding CW."),
    "0404": ("Pause between repeats when a contest-keyer memory is sent as a CW beacon. 1-240 s in "
             "1 s steps, then 270-690 s in 30 s steps. OFF sends the message once, without "
             "repeating."),
    "0405": ("Cut numbers for the automatic contest (serial) number: letters sent in place of "
             "some digits to save time. 1290 = no abbreviation. A = 1, U = 2, N = 9, and O or T = "
             "0. For example AUNT abbreviates 1, 2, 9 and 0 (0 as T), while 12NO only abbreviates "
             "9 (N) and 0 (O)."),
    "0406": ("The contest serial number the keyer will send next (0-9999). It increments as you "
             "send it from a keyer memory."),
    "0407": ("How keyer memory 1 is programmed. TEXT = type the message as characters (MULTI knob "
             "or FH-2 keypad). MESSAGE = record it by sending it on your paddle."),
    "0408": ("How keyer memory 2 is programmed. TEXT = type the message as characters. "
             "MESSAGE = record it by sending it on your paddle."),
    "0409": ("How keyer memory 3 is programmed. TEXT = type the message as characters. "
             "MESSAGE = record it by sending it on your paddle."),
    "0410": ("How keyer memory 4 is programmed. TEXT = type the message as characters. "
             "MESSAGE = record it by sending it on your paddle."),
    "0411": ("How keyer memory 5 is programmed. TEXT = type the message as characters. "
             "MESSAGE = record it by sending it on your paddle."),

    # ------------------------------------------------------------ 05 GENERAL
    "0501": ("Length of the noise blanker's blanking pulse (1, 3 or 10 ms). Short suits sharp "
             "clicks such as ignition noise; longer helps with longer-duration pulse noise."),
    "0502": "How much the noise blanker attenuates noise pulses: 10, 30 or 50 dB.",
    "0503": ("Noise blanker threshold (0-10). Higher blanks more aggressively against pulse noise "
             "such as car ignition, but too high can distort strong signals."),
    "0504": "Volume of the key and alert beeps (0-100). 0 is silent.",
    "0505": ("Function of the front-panel RF/SQL knob. RF = RF gain (useful on SSB/CW). SQL = "
             "squelch (useful on FM and for quiet monitoring)."),
    "0506": ("Baud rate of the USB CAT (computer control) port. Must match the setting in any "
             "program that controls the radio. This program writes it last and reconnects at the "
             "new rate."),
    "0507": ("How long the radio waits for the rest of a CAT command before discarding it. Raise "
             "it if commands from slow or remote connections are being dropped."),
    "0508": ("When ENABLE, the radio watches the RTS line of the CAT port to tell whether the "
             "computer is ready. Keep 'Assert RTS' ticked in Port Options while this is ENABLE, or "
             "set it to DISABLE if your software doesn't raise RTS."),
    "0509": ("Splits the memory channels into six groups so you can scroll through one group at a "
             "time (for example broadcast, contest or repeater channels)."),
    "0510": ("Shows the FM SETTING page in the [F] function screens. That page has the repeater "
             "shift, CTCSS/DCS mode and tone controls used for FM repeater work."),
    "0511": ("Shows the REC SETTING page in the [F] function screens. That page is used to record "
             "and play voice (DVS) and CW keyer memories and to start beacon transmissions."),
    "0512": ("Shows the ATAS SETTING page in the [F] function screens, used to tune an ATAS-120A "
             "active-tuning antenna. Enable it if you use an ATAS (see also 16-15)."),
    "0513": ("Offset applied by Quick Split: one press sets the transmit (VFO-B) frequency this "
             "far from the receive (VFO-A) frequency. -20 to +20 kHz, default +5 kHz, typical for "
             "working DX pile-ups."),
    "0514": ("Transmit time-out timer: forces the radio back to receive after this many minutes of "
             "continuous transmission (1-30 min). Protects against a stuck PTT. OFF disables it."),
    "0515": ("Behaviour of the microphone [UP]/[DWN] keys. ENABLE = holding a key for a second "
             "starts a scan that continues after you let go (press again or key PTT to stop). "
             "DISABLE = the radio only scans while you hold the key."),
    "0516": ("What a scan does when it finds a signal (AM/FM). PAUSE = stop on the signal until it "
             "disappears. TIME = stop for about five seconds, then carry on scanning."),
    "0517": ("Fine calibration of the radio's reference oscillator (-25 to +25). Adjust it while "
             "comparing against a frequency counter or a standard such as WWV. Leave it alone "
             "unless you are calibrating."),
    "0518": ("What the [CLAR] clarifier offsets. RX = receive frequency only (classic RIT). TX = "
             "transmit frequency only (XIT). TRX = both together."),
    "0519": ("Automatic power off: switches the radio off after this many hours without any "
             "button or knob activity. OFF disables it."),
    "0520": ("Cooling fan behaviour. NORMAL = the fan runs only once the radio gets hot. CONTEST = "
             "the fan starts as soon as the temperature begins to rise, which is better for long "
             "high-duty-cycle sessions such as contests and digital modes."),

    # ------------------------------------------------------------ 06 MODE AM
    "0601": _lcut("AM"),
    "0602": _slope("low-cut", "AM", "06-01"),
    "0603": _hcut("AM"),
    "0604": _slope("high-cut", "AM", "06-03"),
    "0605": _mic_select("AM", "16-12 AM DATA GAIN"),
    "0606": _out_level("AM"),
    "0607": _ptt("AM"),

    # ------------------------------------------------------------ 07 MODE CW
    "0701": _lcut("CW", "Combine it with 07-03 to build a narrow audio passband around your CW pitch."),
    "0702": _slope("low-cut", "CW", "07-01"),
    "0703": _hcut("CW", "Default 1200 Hz suits a typical 600-700 Hz CW pitch."),
    "0704": _slope("high-cut", "CW", "07-03"),
    "0705": _out_level("CW"),
    "0706": ("Allows CW keying while the radio is in SSB mode, so you can send CW without "
             "switching modes. OFF = never. 50M = only on 50 MHz. ON = on all bands."),
    "0707": _bfo("CW", auto=True) + " This decides whether received CW is heard on the upper or lower side.",
    "0708": ("CW break-in style. SEMI = the radio stays in transmit for a short delay after you stop "
             "keying (set in 07-09). FULL = full QSK: it returns to receive between every element, "
             "so you can hear the other station between dots."),
    "0709": ("Semi break-in hang time: how long the radio stays in transmit after your last "
             "element before returning to receive (30-3000 ms). Longer avoids switching between "
             "words."),
    "0710": ("Rise and fall time of the CW keying envelope. 4 ms gives softer, cleaner keying with "
             "fewer key clicks; 2 ms is harder and suits very high speeds."),
    "0711": ("How the CW frequency is displayed. FREQ = same dial frequency as in SSB, with no "
             "offset. PITCH = the display includes your CW pitch offset (added or subtracted "
             "depending on the CW BFO side), so it shows the actual transmitted frequency."),
    "0712": ("Lets a computer key CW. OFF = disabled. DAKY = keyed from the DATA PTT pin (pin 3) "
             "of the rear RTTY/DATA jack. RTS or DTR = keyed from that line of the USB virtual COM "
             "port, as used by logging and contest programs."),
    "0713": ("In full break-in (QSK), the delay between keying and the transmit signal starting "
             "(15-30 ms in 5 ms steps). Lengthen it if an external amplifier or relay needs more "
             "time to switch."),

    # ----------------------------------------------------------- 08 MODE DAT
    "0801": ("DATA mode scheme. PSK = set up for PSK (uses the 08-02 tone). OTHERS = for other "
             "sound-card modes (RTTY by AFSK, Olivia, FT8 and so on), using 08-03 and 08-04 for the "
             "display offset and carrier point."),
    "0802": ("Audio centre frequency used for PSK in DATA mode (1000, 1500 or 2000 Hz). Match the "
             "tone your PSK software is centred on."),
    "0803": ("Display offset for DATA mode when 08-01 is OTHERS (-3000 to +3000 Hz, 10 Hz steps). "
             "Shifts the frequency shown on the display, so it can match the frequency your "
             "software or log reports."),
    "0804": ("Carrier point for DATA mode when 08-01 is OTHERS (-3000 to +3000 Hz, 10 Hz steps). "
             "Shifts where the receive and transmit passband sits relative to the dial."),
    "0805": _lcut("DATA", "Lower it, or turn it OFF, for modes such as FT8 that use audio below 300 Hz."),
    "0806": _slope("low-cut", "DATA", "08-05"),
    "0807": _hcut("DATA", "Raise it, or turn it OFF, if your digital software uses tones above 3000 Hz."),
    "0808": _slope("high-cut", "DATA", "08-07"),
    "0809": ("Audio source for DATA transmit. MIC = front microphone jack. REAR = rear RTTY/DATA "
             "jack (typical for a computer interface). The rear input level is set in 16-14."),
    "0810": _ptt("DATA"),
    "0811": ("Level of received audio sent out of the rear RTTY/DATA jack in DATA mode, i.e. what "
             "your sound card hears (PSK31, SSTV and so on). Higher is louder."),
    "0812": _bfo("DATA", auto=False) + (" The factory default is LSB, but most digital-mode software "
                                        "(FT8, PSK31 and so on) expects USB on all bands."),

    # ------------------------------------------------------------ 09 MODE FM
    "0901": _mic_select("FM", "16-13 FM DATA GAIN"),
    "0902": _out_level("FM"),
    "0903": _ptt("FM (packet)"),
    "0904": ("Repeater offset used on 28 MHz (10 m) when a channel or the VFO is set to plus or "
             "minus shift (0-1000 kHz, 10 kHz steps). 10 m repeaters normally use 100 kHz."),
    "0905": ("Repeater offset used on 50 MHz (6 m) when a channel or the VFO is set to plus or "
             "minus shift (0-4000 kHz, 10 kHz steps). Common 6 m offsets are 500 kHz and 1 MHz; "
             "check your local band plan."),
    "0906": ("DCS code polarity for transmit (T) and receive (R): n = normal, iv = inverted. Use "
             "an inverted setting only if a repeater or radio you work with expects reversed DCS."),

    # ----------------------------------------------------------- 10 MODE RTY
    "1001": _lcut("RTTY"),
    "1002": _slope("low-cut", "RTTY", "10-01"),
    "1003": _hcut("RTTY"),
    "1004": _slope("high-cut", "RTTY", "10-03"),
    "1005": ("Where the FSK keying (mark/space shift) signal comes from in RTTY mode. SHIFT = "
             "pin 4 of the rear RTTY/DATA jack (from a terminal unit). DTR or RTS = that line of "
             "the USB virtual COM port, for software FSK."),
    "1006": ("Receive RTTY polarity. NOR = space is below mark (standard). REV = reversed. Use REV "
             "if a station prints garbage that decodes when you invert."),
    "1007": ("Transmit RTTY polarity. NOR = space is below mark (standard). REV = reversed. Leave "
             "it on NOR unless your setup inverts the keying."),
    "1008": "Level of received RTTY audio sent out of the rear RTTY/DATA jack. Higher is louder.",
    "1009": ("RTTY frequency shift between mark and space: 170, 200, 425 or 850 Hz. Amateur RTTY "
             "uses 170 Hz."),
    "1010": ("Audio frequency of the RTTY mark tone: 2125 Hz (high tones, the common amateur "
             "standard) or 1275 Hz (low tones)."),
    "1011": _bfo("RTTY", auto=False) + " Amateur RTTY is conventionally sent on LSB.",

    # ----------------------------------------------------------- 11 MODE SSB
    "1101": _lcut("SSB"),
    "1102": _slope("low-cut", "SSB", "11-01"),
    "1103": _hcut("SSB"),
    "1104": _slope("high-cut", "SSB", "11-03"),
    "1105": _mic_select("SSB", "16-11 SSB DATA GAIN"),
    "1106": _out_level("SSB"),
    "1107": _bfo("SSB", auto=True),
    "1108": _ptt("SSB"),
    "1109": ("Transmit audio bandwidth in SSB (DSP band-pass filter). 300-2700 Hz is the standard "
             "communications sound. 100-3000 Hz is wider and fuller (ragchew). 400-2600 Hz is "
             "narrower and punchier (DX and contests)."),

    # ------------------------------------------------------------ 12 RX DSP
    "1201": ("Bandwidth of the CW audio peak filter (APF): NARROW, MEDIUM or WIDE. The APF centres "
             "on your CW pitch and boosts the wanted signal; narrower is more selective but can "
             "ring."),
    "1202": ("Depth of the CONTOUR filter (-40 to +20). Negative values cut a band of frequencies "
             "(to soften an annoying part of the audio or interference); positive values boost it."),
    "1203": ("Width (Q) of the CONTOUR filter (1-11). Lower numbers affect a narrow slice of the "
             "audio; higher numbers a broad one."),
    "1204": ("Width of the DSP IF notch filter, used to remove a carrier or heterodyne. NARROW "
             "takes out less of the wanted signal; WIDE is more forgiving to tune."),

    # -------------------------------------------------------------- 13 SCOPE
    "1301": ("Automatic repeat sweep of the spectrum scope every 3, 5 or 10 seconds. OFF means "
             "the scope sweeps only when you start it."),
    "1302": ("Width of spectrum shown by the scope: 37.5, 75, 150, 375 or 750 kHz. Narrow spans "
             "show more detail; wide spans show more of the band."),

    # ------------------------------------------------------------- 14 TUNING
    "1401": ("Step size of the MULTI function knob when it is used for quick tuning in SSB, CW, "
             "RTTY and DATA (50, 100 or 500 kHz), for moving quickly across a band."),
    "1402": "Main DIAL tuning step in SSB mode: 2, 5 or 10 Hz per step. Smaller is finer but slower.",
    "1403": "Main DIAL tuning step in AM mode: 10 or 100 Hz per step.",
    "1404": "Main DIAL tuning step in FM mode: 10 or 100 Hz per step.",
    "1405": "Main DIAL tuning step for the remaining modes (CW, RTTY, DATA): 2, 5 or 10 Hz per step.",
    "1406": ("Channel step of the MULTI knob and the microphone [UP]/[DWN] keys in AM mode. 9 kHz "
             "or 10 kHz match broadcast channel spacing in your region. (The Advance Manual lists "
             "the factory default as both 5 kHz and 2.5 kHz.)"),
    "1407": ("Channel step of the MULTI knob and the microphone [UP]/[DWN] keys in FM mode (5 to "
             "25 kHz). Match your local FM channel spacing."),

    # ----------------------------------------------------------- 15 TX AUDIO
    "1501": _eq("low", "100-700 Hz", "freq", False),
    "1502": _eq("low", "", "level", False),
    "1503": _eq("low", "", "bw", False),
    "1504": _eq("middle", "700-1500 Hz", "freq", False),
    "1505": _eq("middle", "", "level", False),
    "1506": _eq("middle", "", "bw", False),
    "1507": _eq("high", "1500-3200 Hz", "freq", False),
    "1508": _eq("high", "", "level", False),
    "1509": _eq("high", "", "bw", False),
    "1510": _eq("low", "100-700 Hz", "freq", True),
    "1511": _eq("low", "", "level", True),
    "1512": _eq("low", "", "bw", True),
    "1513": _eq("middle", "700-1500 Hz", "freq", True),
    "1514": _eq("middle", "", "level", True),
    "1515": _eq("middle", "", "bw", True),
    "1516": _eq("high", "1500-3200 Hz", "freq", True),
    "1517": _eq("high", "", "level", True),
    "1518": _eq("high", "", "bw", True),

    # ----------------------------------------------------------- 16 TX GNRL
    "1601": ("Maximum transmit power for SSB on the HF bands (5-100 W). Use it to cap SSB power, "
             "for example when driving an amplifier."),
    "1602": ("Maximum carrier power for AM on the HF bands (5-40 W). AM peaks are well above the "
             "carrier, so keep this low (25 W default) to protect the final amplifier."),
    "1603": ("Transmit power for the other HF modes (CW, FM, RTTY, DATA), 5-100 W. Consider "
             "reducing it for long digital-mode transmissions."),
    "1604": "Maximum transmit power for SSB on 50 MHz (5-100 W).",
    "1605": "Maximum carrier power for AM on 50 MHz (5-40 W, default 25 W).",
    "1606": "Transmit power for the other modes (CW, FM, RTTY, DATA) on 50 MHz (5-100 W).",
    "1607": ("Microphone gain for SSB (0-100). Set it so ALC just moves on voice peaks; too high "
             "causes distortion and splatter. (The Advance Manual lists the factory default as "
             "both 50 and 30.)"),
    "1608": ("Microphone gain for AM (0-100). Keep it modest to avoid over-modulation. (The "
             "Advance Manual lists the factory default as both 50 and 30.)"),
    "1609": "Microphone gain for FM (0-100). Sets your FM deviation; too high sounds distorted.",
    "1610": ("Audio input level from a TNC or interface into the AFSK modulator (0-100), for "
             "packet and similar DATA operation."),
    "1611": _data_gain("SSB", "11-05 SSB MIC SELECT"),
    "1612": _data_gain("AM", "06-05 AM MIC SELECT"),
    "1613": _data_gain("FM", "09-01 FM MIC SELECT"),
    "1614": _data_gain("DATA", "08-09 DATA IN SELECT"),
    "1615": ("Accessory connected to the rear TUN/LIN jack. OFF = none. EXTERNAL = an external "
             "automatic tuner such as the FC-50 or FC-40. ATAS = an ATAS-120A active-tuning antenna "
             "(also enable 05-12). LAMP = a linear amplifier."),
    "1616": ("Audio that triggers VOX (voice-operated transmit). MIC = the microphone. DATA = audio "
             "on the rear RTTY/DATA jack, so a sound card can key the radio without a PTT line."),
    "1617": ("VOX sensitivity (0-100). Higher makes the radio transmit on quieter sounds. Set it "
             "just high enough that normal speech keys the radio reliably."),
    "1618": ("VOX hang time: how long the radio stays in transmit after you stop talking (30-3000 ms "
             "in 10 ms steps). Too short makes it drop out between words."),
    "1619": ("Anti-VOX: stops sound from the radio's own speaker from triggering VOX. Increase it "
             "until received audio no longer keys the transmitter."),
    "1620": ("VOX sensitivity for DATA VOX (0-100). Set it so the data signal reliably keys the "
             "transmitter and releases it when the data stops."),
    "1621": "Hang time for DATA VOX (30-3000 ms) before returning to receive after the data audio stops.",
    "1622": ("Anti-trip for DATA VOX: keeps received audio from keying the transmitter while "
             "using DATA VOX. Raise it until receive audio no longer triggers transmit."),
    "1623": ("US version only: enables the Alaska emergency channel, 5167.5 kHz (it appears as "
             "memory EMG). Only for stations in or near Alaska, and only for emergencies "
             "(FCC §97.401(c))."),

    # ------------------------------------------------------------ 18 VERSION
    "1801": "Firmware version of the main processor (read only).",
    "1802": "Firmware version of the DSP (read only).",
    "1803": "Firmware version of the display controller (read only).",
}


def help_text(number: str) -> str:
    return MENU_HELP.get(number, "")
