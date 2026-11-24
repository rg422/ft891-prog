"""Memory channel tab."""

from __future__ import annotations

import tkinter as tk
from dataclasses import replace
from tkinter import ttk
from typing import TYPE_CHECKING, Optional

from ..memory import (
    ALL_CHANNELS,
    CLAR_MAX_HZ,
    CTCSS_CODES,
    MODES,
    SHIFT_CODES,
    TAG_LENGTH,
    MemoryChannel,
    channel_label,
    default_mode_for,
    format_freq,
    is_writable,
    parse_freq,
    valid_tag_char,
)
from .widgets import CellEditor, ui_scale

if TYPE_CHECKING:
    from .app import App

SHIFT_LABELS = {"SIMPLEX": "Simplex", "PLUS": "+ (plus)", "MINUS": "- (minus)"}
SHIFT_FROM_LABEL = {v: k for k, v in SHIFT_LABELS.items()}
DISPLAY_LABELS = ("Freq", "Tag")
STATUS_TEXT = {"": "", "new": "new", "modified": "modified", "cleared": "cleared*", "unknown": "to write"}


class MemoryTab(ttk.Frame):
    COLUMNS = ("ch", "freq", "mode", "tag", "display", "clar", "offset", "ctcss", "shift", "status")
    EDITABLE = ("freq", "mode", "tag", "display", "clar", "offset", "ctcss", "shift")

    def __init__(self, master: tk.Misc, app: "App"):
        super().__init__(master, padding=(8, 8, 8, 4))
        self.app = app
        self.model = app.memories
        self.clipboard: list[Optional[MemoryChannel]] = []

        # ---------------------------------------------------------- toolbar
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 6))
        self.btn_read = ttk.Button(bar, text="Read from Radio", command=app.read_memories)
        self.btn_compare = ttk.Button(bar, text="Compare",
                                      command=lambda: app.read_memories(keep_edits=True))
        self.btn_write = ttk.Button(bar, text="Write Changes",
                                    command=lambda: app.write_memories(changed_only=True))
        self.btn_write_all = ttk.Button(bar, text="Write All",
                                        command=lambda: app.write_memories(changed_only=False))
        for b in (self.btn_read, self.btn_compare, self.btn_write, self.btn_write_all):
            b.pack(side="left", padx=(0, 4))
        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(bar, text="Import CSV...", command=app.import_csv).pack(side="left", padx=(0, 4))
        ttk.Button(bar, text="Export CSV...", command=app.export_csv).pack(side="left")

        bar2 = ttk.Frame(self)
        bar2.pack(fill="x", pady=(0, 6))
        ttk.Button(bar2, text="Clear Selected", command=self.clear_selected).pack(side="left", padx=(0, 4))
        ttk.Button(bar2, text="Revert Selected", command=self.revert_selected).pack(side="left", padx=(0, 12))
        self.show_empty = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar2, text="Show empty channels", variable=self.show_empty,
                        command=self.populate).pack(side="left")

        note = ("Double-click a cell to edit (Tab = next field). Del clears, Ctrl+C / Ctrl+V copy and paste "
                "channels. 60 m (5-xx) and EMG channels are read-only.\n"
                "* The FT-891 has no CAT command to erase a memory: cleared channels stay on the radio. "
                "CTCSS tone frequency and repeater offset size are not part of the memory CAT commands "
                "(the offset comes from menus 09-04 / 09-05).")
        self.info = ttk.Label(self, text=note, anchor="w", justify="left", foreground="#505050")
        self.info.pack(side="bottom", fill="x", pady=(6, 0))
        self.info.bind("<Configure>", lambda e: self.info.configure(wraplength=max(200, e.width - 10)))

        # ------------------------------------------------------------- tree
        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(frame, columns=self.COLUMNS, show="headings", selectmode="extended")
        s = ui_scale(self)
        spec = [
            ("ch", "Ch", 50, "center"),
            ("freq", "Freq (MHz)", 105, "e"),
            ("mode", "Mode", 72, "w"),
            ("tag", "Tag", 125, "w"),
            ("display", "Display", 85, "w"),
            ("clar", "Clar", 50, "center"),
            ("offset", "Clar Hz", 70, "e"),
            ("ctcss", "CTCSS", 72, "w"),
            ("shift", "Rpt shift", 85, "w"),
            ("status", "Status", 80, "w"),
        ]
        for col, title, width, anchor in spec:
            self.tree.heading(col, text=title, anchor=anchor)
            self.tree.column(col, width=int(width * s), minwidth=int(40 * s), anchor=anchor,
                             stretch=col in ("tag", "status"))
        ys = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ys.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        self.tree.tag_configure("modified", background="#fff1b8")
        self.tree.tag_configure("new", background="#dff5d8")
        self.tree.tag_configure("unknown", background="#e6f0ff")
        self.tree.tag_configure("cleared", background="#fde0e0")
        self.tree.tag_configure("empty", foreground="#9a9a9a")
        self.tree.tag_configure("readonly", foreground="#707070")

        self.editor = CellEditor(self.tree)
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Return>", lambda e: self._edit_selected("freq"))
        self.tree.bind("<F2>", lambda e: self._edit_selected("freq"))
        self.tree.bind("<Delete>", lambda e: self.clear_selected())
        self.tree.bind("<Control-c>", lambda e: self.copy_selected())
        self.tree.bind("<Control-v>", lambda e: self.paste())
        self.tree.bind("<Button-3>", self._on_right_click)

        self.menu = tk.Menu(self, tearoff=False)
        self.menu.add_command(label="Edit frequency", command=lambda: self._edit_selected("freq"))
        self.menu.add_command(label="Copy", accelerator="Ctrl+C", command=self.copy_selected)
        self.menu.add_command(label="Paste", accelerator="Ctrl+V", command=self.paste)
        self.menu.add_separator()
        self.menu.add_command(label="Clear", accelerator="Del", command=self.clear_selected)
        self.menu.add_command(label="Revert to radio contents", command=self.revert_selected)

        self.populate()

    def action_buttons(self) -> list[ttk.Button]:
        return [self.btn_read, self.btn_compare, self.btn_write, self.btn_write_all]

    # ---------------------------------------------------------------- view
    def _visible(self, ch: str) -> bool:
        return self.show_empty.get() or self.model.values.get(ch) is not None or self.model.status(ch) != ""

    def populate(self) -> None:
        self.editor.cancel()
        selected = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        for ch in ALL_CHANNELS:
            if self._visible(ch):
                self.tree.insert("", "end", iid=ch)
                self.refresh_channel(ch)
        keep = [s for s in selected if self.tree.exists(s)]
        if keep:
            self.tree.selection_set(keep)

    def refresh(self) -> None:
        self.populate()

    def refresh_channel(self, ch: str) -> None:
        if not self.tree.exists(ch):
            if self._visible(ch):
                self.populate()
            return
        m = self.model.values.get(ch)
        status = self.model.status(ch)
        tags: list[str] = []
        if status:
            tags.append(status)
        if m is None:
            tags.append("empty")
            values = (channel_label(ch), "", "", "", "", "", "", "", "", STATUS_TEXT.get(status, status))
        else:
            values = (
                channel_label(ch),
                format_freq(m.freq_hz),
                m.mode,
                m.tag,
                DISPLAY_LABELS[1] if m.tag_on else DISPLAY_LABELS[0],
                "ON" if m.clar_on else "OFF",
                f"{m.clar_offset_hz:+d}" if m.clar_offset_hz else "0",
                m.ctcss,
                SHIFT_LABELS[m.shift],
                STATUS_TEXT.get(status, status),
            )
        if not is_writable(ch):
            tags.append("readonly")
            values = values[:-1] + ("read only",)
        self.tree.item(ch, values=values, tags=tuple(tags))

    # ------------------------------------------------------------- editing
    def _on_double_click(self, event: tk.Event) -> Optional[str]:
        if self.tree.identify_region(event.x, event.y) != "cell":
            return None
        iid = self.tree.identify_row(event.y)
        col_id = self.tree.identify_column(event.x)
        if not iid or not col_id:
            return None
        col = self.COLUMNS[int(col_id[1:]) - 1]
        self.begin_edit(iid, col if col in self.EDITABLE else "freq")
        return "break"

    def _on_right_click(self, event: tk.Event) -> None:
        iid = self.tree.identify_row(event.y)
        if iid:
            if iid not in self.tree.selection():
                self.tree.selection_set(iid)
            self.menu.tk_popup(event.x_root, event.y_root)

    def _edit_selected(self, col: str) -> None:
        sel = self.tree.selection()
        if sel:
            self.begin_edit(sel[0], col)

    def _tab_to(self, ch: str, col: str, direction: int) -> None:
        idx = self.EDITABLE.index(col) + direction
        if 0 <= idx < len(self.EDITABLE):
            self.begin_edit(ch, self.EDITABLE[idx])

    def begin_edit(self, ch: str, col: str) -> None:
        if not is_writable(ch):
            self.bell()
            self.app.status(f"Channel {channel_label(ch)} is read-only.")
            return
        mem = self.model.values.get(ch)
        if mem is None and col != "freq":
            col = "freq"  # an empty channel needs a frequency first
        self.tree.selection_set(ch)
        on_tab = lambda d: self._tab_to(ch, col, d)  # noqa: E731

        def apply(new: MemoryChannel) -> Optional[str]:
            errors = new.validate()
            if errors:
                return "; ".join(errors)
            old = self.model.values.get(ch)
            if old != new:
                self.model.set(ch, new)
                self.app.mark_dirty()
            self.refresh_channel(ch)
            return None

        if col == "freq":
            def commit_freq(text: str) -> Optional[str]:
                try:
                    hz = parse_freq(text)
                except ValueError as exc:
                    return str(exc)
                cur = self.model.values.get(ch)
                new = (MemoryChannel(ch, hz, default_mode_for(hz)) if cur is None
                       else replace(cur, freq_hz=hz))
                return apply(new)

            self.editor.edit(ch, "freq", format_freq(mem.freq_hz) if mem else "", commit_freq, on_tab=on_tab)
            return

        assert mem is not None
        if col == "mode":
            self.editor.edit(ch, col, mem.mode, lambda t: apply(replace(mem, mode=t)),
                             kind="combo", options=MODES, on_tab=on_tab)
        elif col == "tag":
            def commit_tag(text: str) -> Optional[str]:
                bad = sorted({c for c in text if not valid_tag_char(c)})
                if bad:
                    return f"Unsupported characters in tag: {''.join(bad)}"
                tag = text[:TAG_LENGTH]
                new = replace(mem, tag=tag)
                if tag.strip() and not mem.tag.strip() and not mem.tag_on:
                    new = replace(new, tag_on=True)  # typing a tag usually means "show it"
                if not tag.strip():
                    new = replace(new, tag_on=False)
                return apply(new)

            self.editor.edit(ch, col, mem.tag, commit_tag, max_length=TAG_LENGTH, on_tab=on_tab)
        elif col == "display":
            self.editor.edit(ch, col, DISPLAY_LABELS[1] if mem.tag_on else DISPLAY_LABELS[0],
                             lambda t: apply(replace(mem, tag_on=(t == DISPLAY_LABELS[1]))),
                             kind="combo", options=DISPLAY_LABELS, on_tab=on_tab)
        elif col == "clar":
            self.editor.edit(ch, col, "ON" if mem.clar_on else "OFF",
                             lambda t: apply(replace(mem, clar_on=(t == "ON"))),
                             kind="combo", options=("OFF", "ON"), on_tab=on_tab)
        elif col == "offset":
            def commit_offset(text: str) -> Optional[str]:
                try:
                    value = int(float(text.strip().replace("+", "") or "0"))
                except ValueError:
                    return f"'{text}' is not a number of Hz"
                if abs(value) > CLAR_MAX_HZ:
                    return "Clarifier offset must be between -9999 and +9999 Hz"
                return apply(replace(mem, clar_offset_hz=value))

            self.editor.edit(ch, col, str(mem.clar_offset_hz), commit_offset, kind="spin",
                             spin_range=(-CLAR_MAX_HZ, CLAR_MAX_HZ, 10), on_tab=on_tab)
        elif col == "ctcss":
            self.editor.edit(ch, col, mem.ctcss, lambda t: apply(replace(mem, ctcss=t)),
                             kind="combo", options=tuple(CTCSS_CODES.values()), on_tab=on_tab)
        elif col == "shift":
            self.editor.edit(ch, col, SHIFT_LABELS[mem.shift],
                             lambda t: apply(replace(mem, shift=SHIFT_FROM_LABEL[t])),
                             kind="combo", options=[SHIFT_LABELS[s] for s in SHIFT_CODES.values()],
                             on_tab=on_tab)

    # ------------------------------------------------------- bulk actions
    def _selected_writable(self) -> list[str]:
        return [ch for ch in self.tree.selection() if is_writable(ch)]

    def clear_selected(self) -> None:
        chans = [ch for ch in self._selected_writable() if self.model.values.get(ch) is not None]
        if not chans:
            return
        for ch in chans:
            self.model.set(ch, None)
        self.app.mark_dirty()
        self.populate()

    def revert_selected(self) -> None:
        chans = list(self.tree.selection())
        if not chans:
            return
        self.model.revert(chans)
        self.populate()

    def copy_selected(self) -> None:
        sel = [ch for ch in ALL_CHANNELS if ch in self.tree.selection()]
        self.clipboard = [self.model.values.get(ch) for ch in sel]
        if self.clipboard:
            self.app.status(f"Copied {len(self.clipboard)} channel(s).")

    def paste(self) -> None:
        if not self.clipboard:
            return
        sel = self._selected_writable()
        if not sel:
            self.bell()
            return
        writable = [ch for ch in ALL_CHANNELS if is_writable(ch)]
        start = writable.index(min(sel, key=writable.index))
        targets = writable[start:start + len(self.clipboard)]
        for ch, mem in zip(targets, self.clipboard):
            self.model.set(ch, mem.with_channel(ch) if mem is not None else None)
        self.app.mark_dirty()
        self.populate()
        self.tree.selection_set(targets)
        self.app.status(f"Pasted into {len(targets)} channel(s).")
