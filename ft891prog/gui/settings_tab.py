"""Menu settings tab."""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk
from typing import TYPE_CHECKING, Optional

from ..menu_defs import GROUPS, MENU_BY_NUMBER, MENU_ITEMS, MenuItem
from .widgets import CellEditor, ui_scale

if TYPE_CHECKING:
    from .app import App


class SettingsTab(ttk.Frame):
    COLUMNS = ("value", "default", "range", "status")

    def __init__(self, master: tk.Misc, app: "App"):
        super().__init__(master, padding=(8, 8, 8, 4))
        self.app = app
        self.model = app.settings

        # ---------------------------------------------------------- toolbar
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 6))
        self.btn_read = ttk.Button(bar, text="Read from Radio", command=app.read_settings)
        self.btn_compare = ttk.Button(bar, text="Compare",
                                      command=lambda: app.read_settings(keep_edits=True))
        self.btn_write = ttk.Button(bar, text="Write Changes",
                                    command=lambda: app.write_settings(changed_only=True))
        self.btn_write_all = ttk.Button(bar, text="Write All",
                                        command=lambda: app.write_settings(changed_only=False))
        for b in (self.btn_read, self.btn_compare, self.btn_write, self.btn_write_all):
            b.pack(side="left", padx=(0, 4))
        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(bar, text="Revert", command=self.revert_selected).pack(side="left", padx=(0, 4))
        ttk.Button(bar, text="Defaults...", command=self.load_defaults).pack(side="left")

        bar2 = ttk.Frame(self)
        bar2.pack(fill="x", pady=(0, 6))
        ttk.Label(bar2, text="Filter:").pack(side="left", padx=(0, 4))
        self.filter_var = tk.StringVar()
        self.filter_var.trace_add("write", lambda *_: self.populate())
        ttk.Entry(bar2, textvariable=self.filter_var, width=24).pack(side="left", padx=(0, 10))
        self.changed_only = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar2, text="Show changed items only", variable=self.changed_only,
                        command=self.populate).pack(side="left")

        self.info = ttk.Label(self, text="", anchor="w", justify="left")
        self.info.pack(side="bottom", fill="x", pady=(6, 0))
        self.info.bind("<Configure>", lambda e: self.info.configure(wraplength=max(200, e.width - 10)))

        # ------------------------------------------------------------- tree
        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True)
        s = ui_scale(self)
        self.tree = ttk.Treeview(frame, columns=self.COLUMNS, selectmode="extended")
        self.tree.heading("#0", text="Menu item", anchor="w")
        self.tree.heading("value", text="Value", anchor="w")
        self.tree.heading("default", text="Factory default", anchor="w")
        self.tree.heading("range", text="Allowed values", anchor="w")
        self.tree.heading("status", text="Status", anchor="w")
        for col, width, minwidth, stretch in (("#0", 230, 160, False), ("value", 120, 80, False),
                                              ("default", 120, 80, False), ("range", 300, 120, True),
                                              ("status", 80, 60, False)):
            self.tree.column(col, width=int(width * s), minwidth=int(minwidth * s), stretch=stretch)
        ys = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ys.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        bold = tkfont.nametofont("TkDefaultFont").copy()
        bold.configure(weight="bold")
        self._bold = bold
        self.tree.tag_configure("group", font=bold)
        self.tree.tag_configure("changed", background="#fff1b8")
        self.tree.tag_configure("readonly", foreground="#808080")
        self.tree.tag_configure("unknown", foreground="#606060")

        self.editor = CellEditor(self.tree)
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Return>", lambda e: self.edit_selected())
        self.tree.bind("<F2>", lambda e: self.edit_selected())
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._show_info())
        self.tree.bind("<Button-3>", self._on_right_click)

        self.menu = tk.Menu(self, tearoff=False)
        self.menu.add_command(label="Edit", command=self.edit_selected)
        self.menu.add_command(label="Revert to radio value", command=self.revert_selected)
        self.menu.add_command(label="Set to factory default", command=self.default_selected)

        self.populate()

    # ---------------------------------------------------------------- view
    def action_buttons(self) -> list[ttk.Button]:
        return [self.btn_read, self.btn_compare, self.btn_write, self.btn_write_all]

    def _matches(self, item: MenuItem, text: str) -> bool:
        if self.changed_only.get() and not self.model.is_changed(item.number):
            return False
        if not text:
            return True
        hay = f"{item.label} {item.number} {item.name} {item.group_name}".lower()
        return all(word in hay for word in text.lower().split())

    def populate(self) -> None:
        """Rebuild the tree (honouring filter)."""
        self.editor.cancel()
        selected = set(self.tree.selection())
        self.tree.delete(*self.tree.get_children())
        text = self.filter_var.get().strip()
        for group, gname in GROUPS.items():
            items = [i for i in MENU_ITEMS if i.group == group and self._matches(i, text)]
            if not items:
                continue
            gid = f"g{group:02d}"
            self.tree.insert("", "end", iid=gid, text=f"{group:02d}  {gname}", open=True, tags=("group",))
            for item in items:
                self.tree.insert(gid, "end", iid=item.number, text=f"{item.label}  {item.name}")
                self.refresh_item(item.number)
        keep = [s for s in selected if self.tree.exists(s)]
        if keep:
            self.tree.selection_set(keep)
        self._show_info()

    def refresh(self) -> None:
        for item in MENU_ITEMS:
            if self.tree.exists(item.number):
                self.refresh_item(item.number)
        if self.changed_only.get():
            self.populate()
        self._show_info()

    def refresh_item(self, number: str) -> None:
        item = MENU_BY_NUMBER[number]
        value = self.model.values.get(number)
        radio = self.model.radio.get(number)
        tags: tuple[str, ...] = ()
        if item.readonly:
            status, tags = "read only", ("readonly",)
        elif value is None:
            status, tags = "", ("unknown",)
        elif radio is None:
            status = "not read"
        elif value != radio:
            status, tags = "modified", ("changed",)
        else:
            status = ""
        self.tree.item(number, values=(
            item.display(value) if value is not None else "—",
            item.display(item.default) if item.default is not None else "",
            item.range_text(),
            status,
        ), tags=tags)

    def _show_info(self) -> None:
        sel = [s for s in self.tree.selection() if s in MENU_BY_NUMBER]
        if not sel:
            self.info.configure(text="Double-click a value (or press Enter) to edit it. "
                                     "Changed values are highlighted until they are written to the radio.")
            return
        item = MENU_BY_NUMBER[sel[0]]
        value = self.model.values.get(item.number)
        parts = [f"{item.label} {item.name}  ({item.group_name})"]
        if value is not None:
            try:
                parts.append(f"CAT: EX{item.number}{item.encode(value)};")
            except ValueError:
                pass
        parts.append(f"Allowed: {item.range_text()}")
        if item.default is not None:
            parts.append(f"Default: {item.display(item.default)}")
        radio = self.model.radio.get(item.number)
        if radio is not None:
            parts.append(f"In radio: {item.display(radio)}")
        text = "   |   ".join(parts)
        if item.note:
            text += "\n" + item.note
        self.info.configure(text=text)

    # ------------------------------------------------------------- editing
    def _on_double_click(self, event: tk.Event) -> Optional[str]:
        iid = self.tree.identify_row(event.y)
        if iid in MENU_BY_NUMBER:
            self.begin_edit(iid)
            return "break"
        return None

    def _on_right_click(self, event: tk.Event) -> None:
        iid = self.tree.identify_row(event.y)
        if iid:
            if iid not in self.tree.selection():
                self.tree.selection_set(iid)
            self.menu.tk_popup(event.x_root, event.y_root)

    def edit_selected(self) -> None:
        sel = [s for s in self.tree.selection() if s in MENU_BY_NUMBER]
        if sel:
            self.begin_edit(sel[0])

    def begin_edit(self, number: str) -> None:
        item = MENU_BY_NUMBER[number]
        if item.readonly:
            self.bell()
            return
        self.tree.selection_set(number)
        self.tree.focus(number)
        current = self.model.values.get(number)
        if current is None:
            current = item.default if item.default is not None else item.legal_values()[0]
        text = item.display(current)

        def commit(new_text: str) -> Optional[str]:
            try:
                raw = item.parse_display(new_text)
            except ValueError as exc:
                return f"{item.label} {item.name}: {exc}"
            if raw != self.model.values.get(number):
                self.model.set(number, raw)
                self.app.mark_dirty()
            self.refresh_item(number)
            self._show_info()
            return None

        if item.kind == "enum":
            self.editor.edit(number, "value", text, commit, kind="combo", options=item.options())
        elif len(item.legal_values()) <= 500:
            self.editor.edit(number, "value", text, commit, kind="spin", options=item.options())
        else:
            self.editor.edit(number, "value", text, commit, kind="spin",
                             spin_range=(item.minimum / item.scale, item.maximum / item.scale,
                                         item.step / item.scale))

    def _selected_numbers(self) -> list[str]:
        result = []
        for iid in self.tree.selection():
            if iid in MENU_BY_NUMBER:
                result.append(iid)
            else:  # a group row selects all its children
                result.extend(c for c in self.tree.get_children(iid))
        return [n for n in dict.fromkeys(result) if not MENU_BY_NUMBER[n].readonly]

    def revert_selected(self) -> None:
        numbers = self._selected_numbers()
        if not numbers:
            return
        self.model.revert(numbers)
        self.refresh()

    def default_selected(self) -> None:
        numbers = self._selected_numbers()
        for n in numbers:
            item = MENU_BY_NUMBER[n]
            if item.default is not None:
                self.model.set(n, item.default)
        if numbers:
            self.app.mark_dirty()
            self.refresh()

    def load_defaults(self) -> None:
        if not self.app.confirm(
            "Factory defaults",
            "Set every menu item in this program to its factory default value?\n\n"
            "Nothing is sent to the radio until you click Write.",
        ):
            return
        self.model.load_defaults()
        self.app.mark_dirty()
        self.refresh()
