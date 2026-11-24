"""Main window and application controller."""

from __future__ import annotations

import sys
import tkinter as tk
import traceback
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont
from typing import Any, Callable, Optional

from .. import APP_NAME, __version__
from ..cat import (
    BAUD_RATES,
    FT891_ID,
    SIMULATOR_PORT,
    CatError,
    CatTimeout,
    SerialOptions,
    connect,
    guess_cat_port,
    list_serial_ports,
    probe_baud,
)
from ..memory import ALL_CHANNELS, channel_label, is_writable
from ..menu_defs import CAT_RATE, MENU_BY_NUMBER, MENU_ITEMS
from ..model import MemoryModel, SettingsModel
from ..prefs import Prefs
from ..radio import FT891, OperationCancelled, OpResult
from ..storage import export_csv, import_csv, load_profile, save_profile
from .dialogs import PortOptionsDialog, TextDialog
from .memory_tab import MemoryTab
from .settings_tab import SettingsTab
from .widgets import LogPane, ui_scale
from .worker import BackgroundTask, UiDispatcher

SIM_LABEL = f"{SIMULATOR_PORT}  -  built-in radio simulator (no hardware)"
PROFILE_TYPES = [("FT-891 profile", "*.json"), ("All files", "*.*")]
CSV_TYPES = [("CSV file", "*.csv"), ("All files", "*.*")]
RADIO_MENU_NEEDS_CONNECTION = (
    "Read Everything", "Compare Everything", "Write All Changes",
    "Read Menu Settings", "Write Menu Changes", "Read Memories", "Write Memory Changes",
)


class App:
    def __init__(self, root: tk.Tk, simulate: bool = False):
        self.root = root
        self.prefs = Prefs()
        self.settings = SettingsModel()
        self.memories = MemoryModel()
        self.radio: Optional[FT891] = None
        self.radio_info: dict = {}
        self.profile_path: Optional[Path] = None
        self.dirty = False
        self._trace_enabled = False
        self.port_options: dict = {
            "stopbits": int(self.prefs.get("stopbits", 2)),
            "rts": bool(self.prefs.get("rts", True)),
            "dtr": bool(self.prefs.get("dtr", False)),
            "timeout": float(self.prefs.get("timeout", 1.0)),
        }

        self.dispatcher = UiDispatcher(root)
        self.task = BackgroundTask(self.dispatcher, self._on_task_state)

        self._setup_style()
        self._build_menubar()
        self._build_connection_bar()
        self._build_body()
        self._build_statusbar()

        self.refresh_ports(prefer=SIMULATOR_PORT if simulate else None)
        geometry = self.prefs.get("geometry")
        if geometry:
            try:
                self.root.geometry(geometry)
            except tk.TclError:
                pass
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.bind_all("<Control-o>", lambda e: self.open_profile())
        self.root.bind_all("<Control-s>", lambda e: self.save_profile())
        self.update_title()
        self.update_controls()
        self.log(f"{APP_NAME} {__version__} ready. Select the radio's Enhanced COM port and click Connect.")

    # ================================================================ layout
    def _setup_style(self) -> None:
        style = ttk.Style(self.root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        base = tkfont.nametofont("TkDefaultFont")
        line = base.metrics("linespace")
        style.configure("Treeview", rowheight=line + 8)
        style.configure("Status.TLabel", padding=(6, 2))
        style.configure("Conn.TLabel", padding=(8, 0))

    def _build_menubar(self) -> None:
        bar = tk.Menu(self.root)
        file_menu = tk.Menu(bar, tearoff=False)
        file_menu.add_command(label="New", command=self.new_profile)
        file_menu.add_command(label="Open Profile...", accelerator="Ctrl+O", command=self.open_profile)
        file_menu.add_command(label="Save Profile", accelerator="Ctrl+S", command=self.save_profile)
        file_menu.add_command(label="Save Profile As...", command=lambda: self.save_profile(save_as=True))
        file_menu.add_separator()
        file_menu.add_command(label="Import Memories from CSV...", command=self.import_csv)
        file_menu.add_command(label="Export Memories to CSV...", command=self.export_csv)
        file_menu.add_separator()
        file_menu.add_command(label="Save Log...", command=self.save_log)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close)
        bar.add_cascade(label="File", menu=file_menu)

        radio_menu = tk.Menu(bar, tearoff=False)
        radio_menu.add_command(label="Connect", command=self.toggle_connection)
        radio_menu.add_command(label="Auto-detect Baud Rate", command=self.auto_detect)
        radio_menu.add_command(label="Port Options...", command=self.open_port_options)
        radio_menu.add_separator()
        radio_menu.add_command(label="Read Everything", command=lambda: self.read_all(keep_edits=False))
        radio_menu.add_command(label="Compare Everything", command=lambda: self.read_all(keep_edits=True))
        radio_menu.add_command(label="Write All Changes", command=self.write_all_changes)
        radio_menu.add_separator()
        radio_menu.add_command(label="Read Menu Settings", command=self.read_settings)
        radio_menu.add_command(label="Write Menu Changes", command=self.write_settings)
        radio_menu.add_command(label="Read Memories", command=self.read_memories)
        radio_menu.add_command(label="Write Memory Changes", command=self.write_memories)
        bar.add_cascade(label="Radio", menu=radio_menu)

        help_menu = tk.Menu(bar, tearoff=False)
        help_menu.add_command(label="About", command=self.show_about)
        bar.add_cascade(label="Help", menu=help_menu)
        self.root.configure(menu=bar)
        self.radio_menu = radio_menu

    def _build_connection_bar(self) -> None:
        bar = ttk.Frame(self.root, padding=(8, 8, 8, 4))
        bar.pack(fill="x")
        ttk.Label(bar, text="Port:").pack(side="left")
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(bar, textvariable=self.port_var, width=44, state="readonly")
        self.port_combo.pack(side="left", padx=(4, 2))
        self.btn_refresh = ttk.Button(bar, text="Refresh", width=8, command=self.refresh_ports)
        self.btn_refresh.pack(side="left", padx=(0, 10))
        ttk.Label(bar, text="Baud:").pack(side="left")
        self.baud_var = tk.StringVar(value=str(self.prefs.get("baud", 4800)))
        self.baud_combo = ttk.Combobox(bar, textvariable=self.baud_var, width=7, state="readonly",
                                       values=[str(b) for b in BAUD_RATES])
        self.baud_combo.pack(side="left", padx=(4, 6))
        self.btn_options = ttk.Button(bar, text="Options...", command=self.open_port_options)
        self.btn_options.pack(side="left", padx=(0, 10))
        self.btn_connect = ttk.Button(bar, text="Connect", width=11, command=self.toggle_connection)
        self.btn_connect.pack(side="left", padx=(0, 4))
        self.btn_detect = ttk.Button(bar, text="Auto-detect", command=self.auto_detect)
        self.btn_detect.pack(side="left")

        line2 = ttk.Frame(self.root, padding=(8, 0, 8, 4))
        line2.pack(fill="x")
        self.conn_dot = tk.Label(line2, text="●", fg="#a0a0a0", font=("Segoe UI", 10))
        self.conn_dot.pack(side="left")
        self.conn_label = ttk.Label(line2, text="Not connected", style="Conn.TLabel")
        self.conn_label.pack(side="left")

    def _build_body(self) -> None:
        paned = ttk.PanedWindow(self.root, orient="vertical")
        paned.pack(fill="both", expand=True, padx=8)
        self.notebook = ttk.Notebook(paned)
        self.settings_tab = SettingsTab(self.notebook, self)
        self.memory_tab = MemoryTab(self.notebook, self)
        self.notebook.add(self.settings_tab, text="  Menu Settings  ")
        self.notebook.add(self.memory_tab, text="  Memory Channels  ")
        paned.add(self.notebook, weight=5)

        log_frame = ttk.Frame(paned)
        head = ttk.Frame(log_frame)
        head.pack(fill="x", pady=(4, 2))
        ttk.Label(head, text="Log").pack(side="left")
        self.trace_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(head, text="Show CAT traffic", variable=self.trace_var,
                        command=self._trace_toggled).pack(side="left", padx=12)
        ttk.Button(head, text="Clear", width=7, command=lambda: self.log_pane.clear()).pack(side="right")
        self.log_pane = LogPane(log_frame)
        self.log_pane.pack(fill="both", expand=True)
        paned.add(log_frame, weight=1)

    def _build_statusbar(self) -> None:
        bar = ttk.Frame(self.root, padding=(8, 4, 8, 6))
        bar.pack(fill="x")
        self.status_label = ttk.Label(bar, text="", style="Status.TLabel")
        self.status_label.pack(side="left", fill="x", expand=True)
        self.btn_cancel = ttk.Button(bar, text="Cancel", width=8, command=self.task.cancel)
        self.btn_cancel.pack(side="right")
        self.progress = ttk.Progressbar(bar, length=240, mode="determinate")
        self.progress.pack(side="right", padx=8)

    # ============================================================== helpers
    def log(self, message: str, level: str = "info") -> None:
        self.log_pane.log(message, level)

    def status(self, message: str) -> None:
        self.status_label.configure(text=message)

    def confirm(self, title: str, message: str) -> bool:
        return messagebox.askokcancel(title, message, parent=self.root)

    def mark_dirty(self) -> None:
        if not self.dirty:
            self.dirty = True
            self.update_title()

    def update_title(self) -> None:
        name = self.profile_path.name if self.profile_path else "Untitled"
        self.root.title(f"{name}{' *' if self.dirty else ''} - {APP_NAME}")

    def _trace_toggled(self) -> None:
        self._trace_enabled = bool(self.trace_var.get())

    def _trace(self, direction: str, text: str) -> None:
        """Called from the I/O thread."""
        if self._trace_enabled:
            self.dispatcher.post(self.log, f"  {direction} {text}", "trace")

    def _on_task_state(self, busy: bool) -> None:
        self.root.configure(cursor="watch" if busy else "")
        if not busy:
            self.progress.configure(value=0)
        self.update_controls()

    def update_controls(self) -> None:
        busy = self.task.busy
        connected = self.radio is not None
        radio_ok = connected and not busy
        for btn in self.settings_tab.action_buttons() + self.memory_tab.action_buttons():
            btn.state(["!disabled"] if radio_ok else ["disabled"])
        self.btn_connect.configure(text="Disconnect" if connected else "Connect")
        self.btn_connect.state(["disabled"] if busy else ["!disabled"])
        for w in (self.btn_detect, self.btn_options, self.btn_refresh):
            w.state(["disabled"] if busy or connected else ["!disabled"])
        for combo in (self.port_combo, self.baud_combo):
            combo.state(["disabled"] if busy or connected else ["!disabled", "readonly"])
        self.btn_cancel.state(["!disabled"] if busy else ["disabled"])
        self.radio_menu.entryconfigure(0, label="Disconnect" if connected else "Connect",
                                       state="disabled" if busy else "normal")
        self.radio_menu.entryconfigure(1, state="disabled" if busy or connected else "normal")
        for label in RADIO_MENU_NEEDS_CONNECTION:
            self.radio_menu.entryconfigure(label, state="normal" if radio_ok else "disabled")
        self.conn_dot.configure(fg="#2e9e44" if connected else "#a0a0a0")

    def _on_progress(self, done: int, total: int, message: str) -> None:
        self.progress.configure(maximum=max(total, 1), value=done)
        self.status(message)

    def _run(self, title: str, job: Callable, on_success: Callable[[Any], None],
             hint: str = "") -> None:
        if self.task.busy:
            self.root.bell()
            return
        self.log(f"{title}...")
        self.status(f"{title}...")

        def on_error(exc: BaseException) -> None:
            if isinstance(exc, OperationCancelled):
                self.log(f"{title}: cancelled.", "warn")
                self.status("Cancelled.")
                return
            self.status(f"{title} failed.")
            if isinstance(exc, (CatError, OSError, ValueError)):
                self.log(f"{title} failed: {exc}", "error")
            else:
                self.log(f"{title} failed with an unexpected error:\n"
                         + "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)), "error")
            message = f"{title} failed:\n\n{exc}"
            if hint and isinstance(exc, (CatError, OSError)):
                message += "\n\n" + hint
            messagebox.showerror(APP_NAME, message, parent=self.root)

        self.task.start(job, on_success, on_error, self._on_progress)

    def _report(self, title: str, results: list[OpResult], describe: Callable[[str], str]) -> None:
        ok = [r for r in results if r.ok]
        bad = [r for r in results if not r.ok]
        self.log(f"{title}: {len(ok)} succeeded, {len(bad)} failed.", "error" if bad else "ok")
        for r in bad:
            self.log(f"  {describe(r.key)}: {r.message}", "error")
        self.status(f"{title}: {len(ok)} OK" + (f", {len(bad)} failed" if bad else ""))
        if bad:
            lines = [f"{len(ok)} item(s) written and verified, {len(bad)} failed:", ""]
            lines += [f"{describe(r.key)}: {r.message}" for r in bad]
            TextDialog(self.root, title, "\n".join(lines))

    def _require_radio(self) -> Optional[FT891]:
        if self.radio is None:
            messagebox.showinfo(APP_NAME, "Connect to the radio first.", parent=self.root)
        return self.radio

    # =========================================================== connection
    def refresh_ports(self, prefer: Optional[str] = None) -> None:
        ports = list_serial_ports()
        self._port_map: dict[str, str] = {}
        for dev, desc in ports:
            self._port_map[f"{dev}  -  {desc}" if desc and desc != dev else dev] = dev
        self._port_map[SIM_LABEL] = SIMULATOR_PORT
        labels = list(self._port_map)
        self.port_combo.configure(values=labels)
        current = self._selected_port()
        wanted = prefer or current or self.prefs.get("port") or guess_cat_port(ports)
        for label, dev in self._port_map.items():
            if dev == wanted:
                self.port_var.set(label)
                break
        else:
            self.port_var.set(labels[0])
        if not ports:
            self.status("No serial ports found - is the radio's USB cable connected and the CP210x driver installed?")

    def _selected_port(self) -> Optional[str]:
        return getattr(self, "_port_map", {}).get(self.port_var.get())

    def _serial_options(self, baud: Optional[int] = None) -> Optional[SerialOptions]:
        port = self._selected_port()
        if not port:
            messagebox.showerror(APP_NAME, "Select a serial port first.", parent=self.root)
            return None
        return SerialOptions(port=port, baudrate=baud or int(self.baud_var.get()), **self.port_options)

    def open_port_options(self) -> None:
        dlg = PortOptionsDialog(self.root, self.port_options)
        self.root.wait_window(dlg)
        if dlg.result:
            self.port_options.update(dlg.result)
            for k, v in dlg.result.items():
                self.prefs.set(k, v)
            self.prefs.save()
            self.log(f"Port options: {dlg.result['stopbits']} stop bits, RTS {'on' if dlg.result['rts'] else 'off'}, "
                     f"DTR {'on' if dlg.result['dtr'] else 'off'}, timeout {dlg.result['timeout']} s")

    def toggle_connection(self) -> None:
        if self.radio is not None:
            self.disconnect()
        else:
            self.connect()

    def connect(self) -> None:
        opts = self._serial_options()
        if opts is None:
            return
        trace = self._trace

        def job(progress, cancel):
            progress(0, 3, f"Opening {opts.port} at {opts.baudrate} bps")
            cat = connect(opts, trace=trace)
            radio = FT891(cat)
            try:
                progress(1, 3, "Identifying radio")
                rid = radio.identify()
                radio.prepare()
                progress(2, 3, "Reading firmware versions")
                versions = radio.read_versions()
            except BaseException:
                cat.close()
                raise
            return radio, rid, versions

        def done(result) -> None:
            radio, rid, versions = result
            self.radio = radio
            self.radio_info = {"id": rid, "firmware": versions, "port": opts.port, "baud": opts.baudrate}
            sim = " (simulator)" if opts.port == SIMULATOR_PORT else ""
            self.conn_label.configure(text=f"FT-891{sim} on {opts.port} @ {opts.baudrate} bps  -  {versions}")
            self.log(f"Connected to radio ID {rid} on {opts.port} at {opts.baudrate} bps. Firmware: {versions}", "ok")
            self.status("Connected.")
            self.prefs.set("port", opts.port)
            self.prefs.set("baud", opts.baudrate)
            self.prefs.save()
            self.update_controls()
            if rid != FT891_ID:
                messagebox.showwarning(
                    APP_NAME,
                    f"The radio identifies as {rid}, not an FT-891 ({FT891_ID}).\n\n"
                    "Menu numbers and memory formats may differ. Write to it at your own risk.",
                    parent=self.root)

        self._run(f"Connecting to {opts.port}", job, done, hint=(
            "Check that:\n"
            " - the radio is switched on and the USB cable is connected\n"
            " - you picked the 'Enhanced COM Port' (not the 'Standard' one)\n"
            " - the baud rate matches menu 05-06 CAT RATE (try Auto-detect)\n"
            " - no other program (WSJT-X, logger, flrig...) has the port open"))

    def auto_detect(self) -> None:
        opts = self._serial_options()
        if opts is None:
            return
        trace = self._trace

        def job(progress, cancel):
            progress(0, 1, f"Trying 4800-38400 bps on {opts.port}")
            found = probe_baud(opts, trace)
            if found is None:
                raise CatError("The radio did not answer at any CAT rate (4800, 9600, 19200, 38400 bps).")
            return found

        def done(found) -> None:
            baud, rid = found
            self.baud_var.set(str(baud))
            self.log(f"Radio (ID {rid}) answered at {baud} bps.", "ok")
            self.connect()

        self._run("Auto-detecting baud rate", job, done, hint=(
            "Check the port selection, cable and that the radio is on. "
            "If menu 05-08 CAT RTS is ENABLE, keep 'Assert RTS' ticked in Port Options."))

    def disconnect(self) -> None:
        if self.radio is not None:
            self.radio.cat.close()
            self.log("Disconnected.")
        self.radio = None
        self.conn_label.configure(text="Not connected")
        self.status("Disconnected.")
        self.update_controls()

    # ======================================================= settings I/O
    def read_settings(self, keep_edits: bool = False) -> None:
        radio = self._require_radio()
        if radio is None:
            return
        if not keep_edits and self.settings.changed_items() and not self.confirm(
                "Read menu settings",
                "Replace your unsaved menu edits with the values in the radio?\n\n"
                "(Use 'Compare with Radio' to keep your values and see the differences.)"):
            return
        items = list(MENU_ITEMS)

        def job(progress, cancel):
            return radio.read_menus(items, progress, cancel)

        def done(result) -> None:
            values, problems = result
            self.settings.apply_radio(values, keep_edits=keep_edits)
            self.settings_tab.refresh()
            verb = "Compared" if keep_edits else "Read"
            self.log(f"{verb} {len(values)} menu items.", "ok")
            for p in problems:
                self.log(f"  {self._describe_menu(p.key)}: {p.message}", "warn")
            if keep_edits:
                n = len(self.settings.changed_items())
                self.status(f"{n} menu item(s) differ from the radio.")
                self.log(f"{n} menu item(s) differ from the radio.")
            else:
                self.status(f"Read {len(values)} menu items from the radio.")

        self._run("Comparing menu settings" if keep_edits else "Reading menu settings", job, done)

    def write_settings(self, changed_only: bool = True) -> None:
        radio = self._require_radio()
        if radio is None:
            return
        items = self.settings.changed_items() if changed_only else self.settings.all_items()
        if not items:
            messagebox.showinfo(APP_NAME, "There are no menu changes to write." if changed_only else
                                "No menu values loaded. Read from the radio or open a profile first.",
                                parent=self.root)
            return
        preview = "\n".join(f"  {i.label} {i.name} = {i.display(v)}" for i, v in items[:12])
        if len(items) > 12:
            preview += f"\n  ... and {len(items) - 12} more"
        warn = ""
        for item, raw in items:
            if item.number == CAT_RATE and BAUD_RATES[raw] != radio.cat.baudrate:
                warn = (f"\n\nCAT RATE will change to {item.display(raw)}. It is written last and the "
                        "program will reconnect at the new rate.")
        if not self.confirm("Write menu settings", f"Write {len(items)} menu setting(s) to the radio?\n\n"
                                                   f"{preview}{warn}"):
            return
        written = {i.number: v for i, v in items}

        def job(progress, cancel):
            return radio.write_menus(items, progress, cancel)

        def done(results: list[OpResult]) -> None:
            for r in results:
                if r.ok:
                    self.settings.mark_written(r.key, written[r.key])
                    if r.key == CAT_RATE:
                        self._after_cat_rate_change()
            self.settings_tab.refresh()
            self._report("Write menu settings", results, self._describe_menu)

        self._run("Writing menu settings", job, done)

    def _after_cat_rate_change(self) -> None:
        if self.radio is None:
            return
        baud = self.radio.cat.baudrate
        self.baud_var.set(str(baud))
        self.prefs.set("baud", baud)
        self.prefs.save()
        port = self.radio_info.get("port", "")
        self.radio_info["baud"] = baud
        self.conn_label.configure(text=f"FT-891 on {port} @ {baud} bps  -  {self.radio_info.get('firmware', '')}")

    @staticmethod
    def _describe_menu(number: str) -> str:
        item = MENU_BY_NUMBER.get(number)
        return f"{item.label} {item.name}" if item else number

    # ======================================================== memory I/O
    def read_memories(self, keep_edits: bool = False) -> None:
        radio = self._require_radio()
        if radio is None:
            return
        if not keep_edits and self.memories.changed_channels() and not self.confirm(
                "Read memories",
                "Replace your unsaved memory edits with the channels in the radio?\n\n"
                "(Use 'Compare with Radio' to keep your channels and see the differences.)"):
            return

        def job(progress, cancel):
            return radio.read_memories(ALL_CHANNELS, progress, cancel)

        def done(result) -> None:
            data, problems = result
            self._apply_memories(data, keep_edits)
            for p in problems:
                self.log(f"  channel {channel_label(p.key)}: {p.message}", "warn")

        self._run("Comparing memories" if keep_edits else "Reading memories", job, done)

    def _apply_memories(self, data: dict, keep_edits: bool) -> None:
        radio = self.radio
        self.memories.apply_radio(data, keep_edits=keep_edits)
        if radio is not None:
            self.memories.compare_tags = radio.tag_read_supported is not False
        self.memory_tab.refresh()
        used = sum(1 for m in data.values() if m is not None)
        self.log(f"{'Compared' if keep_edits else 'Read'} {len(data)} channels ({used} in use).", "ok")
        if radio is not None and radio.tag_read_supported is False:
            self.log("  This radio does not return memory tags over CAT, so tags are shown blank. "
                     "Tags you enter are still written.", "warn")
        if keep_edits:
            n = len(self.memories.changed_channels())
            self.status(f"{n} memory channel(s) differ from the radio.")
            self.log(f"{n} memory channel(s) differ from the radio.")
        else:
            self.status(f"Read {used} memory channels from the radio.")

    def write_memories(self, changed_only: bool = True) -> None:
        radio = self._require_radio()
        if radio is None:
            return
        mems = self.memories.changed_channels() if changed_only else self.memories.all_channels()
        cleared = self.memories.cleared_channels()
        invalid = [(m, m.validate()) for m in mems if m.validate()]
        if invalid:
            text = "\n".join(f"{channel_label(m.channel)}: {'; '.join(e)}" for m, e in invalid)
            messagebox.showerror(APP_NAME, f"Fix these channels first:\n\n{text}", parent=self.root)
            return
        note = ""
        if cleared:
            names = ", ".join(channel_label(c) for c in cleared[:10]) + (" ..." if len(cleared) > 10 else "")
            note = (f"\n\n{len(cleared)} channel(s) you cleared ({names}) cannot be erased over CAT and "
                    "will stay on the radio - delete them on the radio itself.")
        if not mems:
            messagebox.showinfo(APP_NAME, ("There are no memory changes to write." if changed_only
                                           else "There are no memory channels to write.") + note,
                                parent=self.root)
            return
        preview = ", ".join(channel_label(m.channel) for m in mems[:20]) + (" ..." if len(mems) > 20 else "")
        if not self.confirm("Write memories",
                            f"Write {len(mems)} memory channel(s) to the radio?\n\n{preview}{note}"):
            return
        written = {m.channel: m for m in mems}

        def job(progress, cancel):
            return radio.write_memories(mems, progress, cancel)

        def done(results: list[OpResult]) -> None:
            for r in results:
                if r.ok:
                    self.memories.mark_written(r.key, written[r.key])
            self.memory_tab.refresh()
            self._report("Write memories", results, lambda ch: f"channel {channel_label(ch)}")

        self._run("Writing memories", job, done)

    # ============================================================ combined
    def read_all(self, keep_edits: bool = False) -> None:
        radio = self._require_radio()
        if radio is None:
            return
        if not keep_edits and (self.settings.changed_items() or self.memories.changed_channels()) and \
                not self.confirm("Read everything", "Replace your unsaved edits with the radio's contents?"):
            return

        def job(progress, cancel):
            menus = radio.read_menus(MENU_ITEMS, progress, cancel)
            mems = radio.read_memories(ALL_CHANNELS, progress, cancel)
            return menus, mems

        def done(result) -> None:
            (values, menu_problems), (data, mem_problems) = result
            self.settings.apply_radio(values, keep_edits=keep_edits)
            self.settings_tab.refresh()
            self.log(f"{'Compared' if keep_edits else 'Read'} {len(values)} menu items.", "ok")
            for p in menu_problems:
                self.log(f"  {self._describe_menu(p.key)}: {p.message}", "warn")
            self._apply_memories(data, keep_edits)
            for p in mem_problems:
                self.log(f"  channel {channel_label(p.key)}: {p.message}", "warn")
            if keep_edits:
                self.status(f"{len(self.settings.changed_items())} menu item(s) and "
                            f"{len(self.memories.changed_channels())} channel(s) differ from the radio.")

        self._run("Comparing with radio" if keep_edits else "Reading radio", job, done)

    def write_all_changes(self) -> None:
        radio = self._require_radio()
        if radio is None:
            return
        items = self.settings.changed_items()
        mems = self.memories.changed_channels()
        if not items and not mems:
            messagebox.showinfo(APP_NAME, "There are no changes to write.", parent=self.root)
            return
        bad = [m for m in mems if m.validate()]
        if bad:
            messagebox.showerror(APP_NAME, "Some memory channels have invalid values; fix them on the "
                                           "Memory Channels tab first.", parent=self.root)
            return
        if not self.confirm("Write all changes", f"Write {len(items)} menu setting(s) and {len(mems)} memory "
                                                 "channel(s) to the radio?"):
            return
        written_menu = {i.number: v for i, v in items}
        written_mem = {m.channel: m for m in mems}

        def job(progress, cancel):
            mem_results = radio.write_memories(mems, progress, cancel) if mems else []
            menu_results = radio.write_menus(items, progress, cancel) if items else []
            return menu_results, mem_results

        def done(result) -> None:
            menu_results, mem_results = result
            for r in menu_results:
                if r.ok:
                    self.settings.mark_written(r.key, written_menu[r.key])
                    if r.key == CAT_RATE:
                        self._after_cat_rate_change()
            for r in mem_results:
                if r.ok:
                    self.memories.mark_written(r.key, written_mem[r.key])
            self.settings_tab.refresh()
            self.memory_tab.refresh()
            results = menu_results + mem_results

            def describe(key: str) -> str:
                return self._describe_menu(key) if key in MENU_BY_NUMBER else f"channel {channel_label(key)}"

            self._report("Write all changes", results, describe)

        self._run("Writing changes", job, done)

    # =============================================================== files
    def _ask_save_changes(self) -> bool:
        """Returns False if the user cancelled."""
        if not self.dirty:
            return True
        answer = messagebox.askyesnocancel(APP_NAME, "Save your changes to a profile first?", parent=self.root)
        if answer is None:
            return False
        if answer:
            return self.save_profile()
        return True

    def new_profile(self) -> None:
        if not self._ask_save_changes():
            return
        self.settings.clear()
        self.memories.clear()
        self.profile_path = None
        self.dirty = False
        self.settings_tab.refresh()
        self.memory_tab.refresh()
        self.update_title()
        self.log("Started a new, empty profile.")

    def open_profile(self) -> None:
        if not self._ask_save_changes():
            return
        path = filedialog.askopenfilename(parent=self.root, title="Open profile", filetypes=PROFILE_TYPES,
                                          initialdir=self.prefs.get("last_dir") or None)
        if not path:
            return
        p = Path(path)
        try:
            warnings = load_profile(p, self.settings, self.memories)
        except (OSError, ValueError) as exc:
            messagebox.showerror(APP_NAME, f"Could not open {p.name}:\n\n{exc}", parent=self.root)
            return
        self.profile_path = p
        self.dirty = False
        self.prefs.set("last_dir", str(p.parent))
        self.prefs.save()
        self.settings_tab.refresh()
        self.memory_tab.refresh()
        self.update_title()
        self.log(f"Opened profile {p}.", "ok")
        for w in warnings:
            self.log(f"  {w}", "warn")
        self.status("Profile loaded. Use 'Compare with Radio' to see what differs, then write.")

    def save_profile(self, save_as: bool = False) -> bool:
        path = self.profile_path
        if save_as or path is None:
            initial = f"ft891-{datetime.now():%Y%m%d}.json"
            chosen = filedialog.asksaveasfilename(parent=self.root, title="Save profile", filetypes=PROFILE_TYPES,
                                                  defaultextension=".json", initialfile=initial,
                                                  initialdir=self.prefs.get("last_dir") or None)
            if not chosen:
                return False
            path = Path(chosen)
        try:
            save_profile(path, self.settings, self.memories, self.radio_info)
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"Could not save {path.name}:\n\n{exc}", parent=self.root)
            return False
        self.profile_path = path
        self.dirty = False
        self.prefs.set("last_dir", str(path.parent))
        self.prefs.save()
        self.update_title()
        self.log(f"Saved profile {path}.", "ok")
        self.status(f"Saved {path.name}.")
        return True

    def import_csv(self) -> None:
        path = filedialog.askopenfilename(parent=self.root, title="Import memories from CSV",
                                          filetypes=CSV_TYPES, initialdir=self.prefs.get("last_dir") or None)
        if not path:
            return
        try:
            channels, warnings = import_csv(Path(path))
        except (OSError, ValueError, UnicodeDecodeError) as exc:
            messagebox.showerror(APP_NAME, f"Could not import {Path(path).name}:\n\n{exc}", parent=self.root)
            return
        for w in warnings:
            self.log(f"  CSV {w}", "warn")
        if not channels:
            messagebox.showwarning(APP_NAME, "No valid channels found in that file.", parent=self.root)
            return
        replace_all = messagebox.askyesnocancel(
            APP_NAME,
            f"Import {len(channels)} channel(s).\n\n"
            "Yes = replace ALL memory channels with the file's contents (others become empty)\n"
            "No = merge: only overwrite the channel numbers present in the file",
            parent=self.root)
        if replace_all is None:
            return
        if replace_all:
            for ch in ALL_CHANNELS:
                if ch not in channels and is_writable(ch):
                    self.memories.set(ch, None)
        skipped = [ch for ch in channels if not is_writable(ch)]
        for ch, mem in channels.items():
            if is_writable(ch):
                self.memories.set(ch, mem)
        if skipped:
            self.log(f"  Skipped read-only channel(s): {', '.join(channel_label(c) for c in skipped)}", "warn")
        self.mark_dirty()
        self.memory_tab.refresh()
        self.notebook.select(self.memory_tab)
        self.log(f"Imported {len(channels)} channel(s) from {path}"
                 + (f" ({len(warnings)} line(s) skipped)" if warnings else "") + ".", "ok")

    def export_csv(self) -> None:
        path = filedialog.asksaveasfilename(parent=self.root, title="Export memories to CSV",
                                            filetypes=CSV_TYPES, defaultextension=".csv",
                                            initialfile=f"ft891-memories-{datetime.now():%Y%m%d}.csv",
                                            initialdir=self.prefs.get("last_dir") or None)
        if not path:
            return
        try:
            n = export_csv(Path(path), self.memories)
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"Could not export:\n\n{exc}", parent=self.root)
            return
        self.log(f"Exported {n} channel(s) to {path}.", "ok")

    def save_log(self) -> None:
        path = filedialog.asksaveasfilename(parent=self.root, title="Save log", defaultextension=".txt",
                                            filetypes=[("Text file", "*.txt")],
                                            initialfile=f"ft891-log-{datetime.now():%Y%m%d-%H%M}.txt")
        if path:
            Path(path).write_text(self.log_pane.get_text(), encoding="utf-8")

    # ================================================================ misc
    def show_about(self) -> None:
        messagebox.showinfo(
            f"About {APP_NAME}",
            f"{APP_NAME} {__version__}\n\n"
            "Reads, edits and writes Yaesu FT-891 menu settings and memory channels over the "
            "radio's USB CAT port.\n\n"
            "Based on the Yaesu FT-891 CAT Operation Reference Book.\n"
            "Not affiliated with Yaesu Musen Co., Ltd.\n\n"
            "Copyright (c) 2026 Ryan Gedminas. Released under the MIT License.\n\n"
            "Always save a backup profile before writing to your radio.",
            parent=self.root)

    def on_close(self) -> None:
        if self.task.busy:
            if not self.confirm(APP_NAME, "A radio operation is still running. Cancel it and quit?"):
                return
            self.task.cancel()
        if not self._ask_save_changes():
            return
        if self.radio is not None:
            self.radio.cat.close()
        try:
            self.prefs.set("geometry", self.root.geometry())
            self.prefs.save()
        except tk.TclError:
            pass
        self.root.destroy()


def _enable_dpi_awareness() -> None:
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass


def _icon_path() -> Optional[Path]:
    """Locate assets/ft891.ico both from a source checkout and inside a PyInstaller build."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    path = base / "assets" / "ft891.ico"
    return path if path.exists() else None


def run(simulate: bool = False) -> None:
    _enable_dpi_awareness()
    root = tk.Tk()
    icon = _icon_path()
    if icon is not None and sys.platform == "win32":
        try:
            root.iconbitmap(default=str(icon))
        except tk.TclError:
            pass
    s = ui_scale(root)
    width = min(int(1100 * s), root.winfo_screenwidth() - 40)
    height = min(int(760 * s), root.winfo_screenheight() - 80)
    root.geometry(f"{width}x{height}")
    root.minsize(int(820 * s), int(520 * s))
    App(root, simulate=simulate)
    root.mainloop()
