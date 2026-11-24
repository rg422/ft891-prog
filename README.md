# FT-891 Programmer

A Windows desktop program (Python + Tkinter) to **read, edit and write the menu settings and
memory channels of a Yaesu FT-891** over its USB CAT port. It can also save everything to a
profile file for backup and restore, and import or export memory channels as CSV.

> Not affiliated with Yaesu Musen Co., Ltd. Save a backup profile before you write to the radio.

## Features

- **Menu settings**: every menu item 01-01 to 16-23 (158 items, plus the firmware versions in
  18-xx). Values are shown as the radio shows them (`300 msec`, `ELEKEY-B`, `+5 kHz`...), with
  factory defaults, allowed ranges and the exact CAT command for each item.
- **Built-in help**: select any menu item to see a plain-language explanation of what it does
  and when you would change it. The search box also searches these descriptions, so typing
  "amplifier" or "VOX" finds the relevant items.
- **Memory channels**: 01-99 and the PMS pairs P1L-P9U, with frequency, mode, 12-character tag
  (and whether the radio displays the tag or the frequency), clarifier, CTCSS mode and repeater
  shift. The 60 m channels (5-01 to 5-10) and EMG are shown read-only.
- **Safe writes**: only changed items are sent by default. Every write is read back and
  checked, and a report lists anything the radio did not accept.
- **Compare with radio**: open a saved profile, click *Compare*, and the program highlights
  what differs from the radio. *Write Changes* then sends only those differences.
- **Profiles**: menus and memories in one `.json` file. **CSV** import/export for memories, so
  you can edit them in a spreadsheet.
- **Auto-detect** finds the CAT baud rate. Changing menu 05-06 CAT RATE is handled: the
  program writes it last and reconnects at the new rate.
- **Built-in simulator**: pick the `SIMULATOR` port to try everything without a radio.
- CAT traffic log, cancellable operations, and high-DPI aware layout.

## Running from source

Requires Python 3.10+ on Windows (Tkinter is included with the python.org installer).

```powershell
python -m pip install -r requirements.txt
```

```powershell
python -m ft891prog
```

Use `python -m ft891prog --simulate` to start with the simulator selected.

## Using it

1. Connect the FT-891 to the PC with a USB cable. If Windows does not find it, install the
   USB driver (Silicon Labs CP210x virtual COM port) from the Yaesu website. The radio
   appears as **two** COM ports. Pick the **Enhanced COM Port** for CAT; the Standard port is
   for PTT and CW keying.
2. Choose the baud rate that matches menu **05-06 CAT RATE** (factory default 4800), or click
   **Auto-detect**. Close any other program that uses the port (WSJT-X, flrig, loggers).
3. Click **Connect**, then **Read from Radio** on either tab (or *Radio > Read Everything*).
4. Double-click a value to change it. Changed rows turn yellow; new memory channels turn green.
5. Click **Write Changes** to send just the edits, or **Write All** to send every value.
6. Use **File > Save Profile** to keep a backup. To restore one: open it, click **Compare**,
   then **Write Changes**.

### Memory editing tips

- Frequencies can be typed as `14.250`, `14.250.000`, `7074 kHz` or `14250000`.
- Tab moves to the next field; Del clears; Ctrl+C / Ctrl+V copy and paste channels (pasting
  fills consecutive channels starting at the selected one).
- Typing a tag also switches the channel's display to *Tag*. Change the *Display* column back
  to *Freq* if you want the radio to show the frequency.

### Port options

*Radio > Port Options* sets the serial stop bits (default 2, as Hamlib uses for Yaesu radios),
the RTS line (keep it on while menu 05-08 CAT RTS is ENABLE) and DTR. DTR stays off by default
because the radio can be configured to key PTT or CW from it.

## Limitations of the FT-891 CAT protocol

These are limits of the radio's CAT command set, not of this program:

- **Memories cannot be erased over CAT.** A channel you clear here stays on the radio. Delete it
  on the radio itself.
- **CTCSS tone frequency** and the **repeater offset amount** are not part of the memory
  read/write commands. The memory stores the CTCSS *mode* and the shift *direction*. The offset
  amount comes from menus 09-04 and 09-05.
- **Memory tags**: the CAT manual lists `MT` as a write command. The program also tries it as a
  read command. If the radio does not answer, tags show blank and a note is logged. Tags you type
  are still written. When tags can't be read and a channel has no tag, the program writes with
  `MW` so an existing tag on the radio is left alone.
- Menu **17-01 RESET** is deliberately left out.

## Building the Windows .exe

```powershell
.\build.ps1
```

The script creates `.venv`, installs the requirements and PyInstaller, runs the tests, and
builds a single-file, no-console executable:

- `dist\FT891Programmer.exe`
- `dist\FT891Programmer-v<version>-win64.zip` (the exe plus this README, ready to attach to a
  release)

Bump `__version__` in `ft891prog/__init__.py` before building a new release.

## Development

```powershell
python -m pip install -r requirements-dev.txt
```

```powershell
python -m pytest
```

The tests cover the menu tables, the memory encoding, profile and CSV round trips, and complete
read/write sessions against the simulator.

### Layout

| Path | Purpose |
| --- | --- |
| `ft891prog/cat.py` | Serial port setup, `;`-framed request/response, error and timeout handling, baud probing |
| `ft891prog/menu_defs.py` | Every EX menu item: CAT number, width, encoding, labels, ranges, defaults |
| `ft891prog/menu_help.py` | Plain-language description of every menu item, shown in the Settings tab |
| `ft891prog/memory.py` | Memory channel model and `MR` / `MW` / `MT` encoding, frequency parsing |
| `ft891prog/radio.py` | High-level read/write of menus and memories, with verification |
| `ft891prog/simulator.py` | FT-891 CAT emulator used by the `SIMULATOR` port and the tests |
| `ft891prog/model.py` | Edited values vs. values known to be in the radio (change tracking) |
| `ft891prog/storage.py` | JSON profiles and CSV import/export |
| `ft891prog/gui/` | Tkinter user interface |
| `build.ps1` | PyInstaller build |
| `docs/manuals/` | Local copies of the Yaesu manuals (not committed) and where to download them |

### Protocol references

- Yaesu *FT-891 CAT Operation Reference Book*: command formats, EX menu table, memory channel
  layout.
- Yaesu *FT-891 Advance Manual*: menu names, ranges, factory defaults, and what each menu item
  does.
- Yaesu *FT-891 Operating Manual*: installation and basic operation.

See [docs/manuals/README.md](docs/manuals/README.md) for download links.

The Advance Manual contradicts itself on three factory defaults: 14-06 AM CH STEP (5 or
2.5 kHz), 16-07 SSB MIC GAIN and 16-08 AM MIC GAIN (50 or 30). The program uses the menu
table's values (5 kHz, 50 and 50), and the help text for those items mentions the discrepancy.

One known erratum: the CAT manual gives menu 09-05 (RPT SHIFT 50MHz) a 1-digit parameter, but
its range (0000-4000) needs 4. The program uses 4. When writing, it always uses the field width
the radio itself returned when that item was read.
