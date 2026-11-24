"""Reusable Tk widgets: in-place Treeview cell editor and a log pane."""

from __future__ import annotations

import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Optional, Sequence

CommitFn = Callable[[str], Optional[str]]   # returns an error message or None


def ui_scale(widget: tk.Misc) -> float:
    """Display scale factor (1.0 at 96 DPI, 1.5 at 150 % Windows scaling)."""
    try:
        return max(1.0, widget.winfo_fpixels("1i") / 96.0)
    except tk.TclError:
        return 1.0


class CellEditor:
    """Overlay an Entry / Combobox / Spinbox on a Treeview cell.

    ``on_commit`` receives the text; if it returns a string, that string is
    shown as an error and the edit is discarded.
    """

    def __init__(self, tree: ttk.Treeview):
        self.tree = tree
        self.widget: Optional[tk.Widget] = None
        self._on_commit: Optional[CommitFn] = None
        self._on_tab: Optional[Callable[[int], None]] = None
        self._done = False
        tree.bind("<MouseWheel>", lambda e: self.commit(), add="+")
        tree.bind("<Configure>", lambda e: self.cancel(), add="+")

    @property
    def active(self) -> bool:
        return self.widget is not None

    def edit(
        self,
        iid: str,
        column: str,
        value: str,
        on_commit: CommitFn,
        *,
        kind: str = "entry",
        options: Optional[Sequence[str]] = None,
        spin_range: Optional[tuple[float, float, float]] = None,
        on_tab: Optional[Callable[[int], None]] = None,
        max_length: Optional[int] = None,
    ) -> None:
        self.cancel()
        self.tree.see(iid)
        self.tree.update_idletasks()
        bbox = self.tree.bbox(iid, column)
        if not bbox:
            return
        x, y, w, h = bbox
        if kind == "combo":
            widget = ttk.Combobox(self.tree, values=list(options or []), state="readonly")
            widget.set(value)
            widget.bind("<<ComboboxSelected>>", lambda e: self.commit())
        elif kind == "spin":
            if options:
                widget = ttk.Spinbox(self.tree, values=list(options), wrap=False)
            else:
                lo, hi, step = spin_range or (0, 100, 1)
                widget = ttk.Spinbox(self.tree, from_=lo, to=hi, increment=step, wrap=False)
            widget.set(value)
            widget.selection_range(0, tk.END)
        else:
            var = tk.StringVar(value=value)
            if max_length:
                var.trace_add("write", lambda *_: len(var.get()) > max_length and var.set(var.get()[:max_length]))
            widget = ttk.Entry(self.tree, textvariable=var)
            widget._var = var  # type: ignore[attr-defined]  # keep a reference
            widget.selection_range(0, tk.END)
        widget.place(x=x, y=y, width=max(w, 110), height=h)
        widget.focus_set()
        widget.bind("<Return>", lambda e: (self.commit(), "break")[1])
        widget.bind("<KP_Enter>", lambda e: (self.commit(), "break")[1])
        widget.bind("<Escape>", lambda e: (self.cancel(), "break")[1])
        widget.bind("<Tab>", lambda e: (self._tab(1), "break")[1])
        widget.bind("<Shift-Tab>", lambda e: (self._tab(-1), "break")[1])
        widget.bind("<FocusOut>", self._focus_out)
        self.widget = widget
        self._on_commit = on_commit
        self._on_tab = on_tab
        self._done = False

    def _tab(self, direction: int) -> None:
        on_tab = self._on_tab
        if self.commit() and on_tab is not None:
            on_tab(direction)

    def _focus_out(self, _event: tk.Event) -> None:
        self.tree.after(10, self._check_focus)

    def _check_focus(self) -> None:
        if self.widget is None:
            return
        try:
            focus = self.tree.focus_get()
        except KeyError:  # focus is inside a combobox drop-down (Tk-internal widget)
            return
        if focus is not None and str(focus).startswith(str(self.widget)):
            return
        if focus is None and isinstance(self.widget, ttk.Combobox):
            return  # drop-down list is open
        self.commit()

    def commit(self) -> bool:
        """Apply the edit.  Returns True when the value was accepted."""
        if self.widget is None or self._done:
            return False
        self._done = True
        text = self.widget.get()  # type: ignore[attr-defined]
        callback = self._on_commit
        self._destroy()
        if callback is None:
            return False
        error = callback(text)
        if error:
            self.tree.bell()
            messagebox.showerror("Invalid value", error, parent=self.tree.winfo_toplevel())
            return False
        self.tree.focus_set()
        return True

    def cancel(self) -> None:
        if self.widget is not None:
            self._done = True
            self._destroy()
            self.tree.focus_set()

    def _destroy(self) -> None:
        widget, self.widget = self.widget, None
        if widget is not None:
            widget.destroy()


class LogPane(ttk.Frame):
    MAX_LINES = 4000

    def __init__(self, master: tk.Misc, **kw):
        super().__init__(master, **kw)
        self.text = tk.Text(self, height=7, wrap="none", state="disabled", relief="flat",
                            font=("Consolas", 9), borderwidth=0, padx=6, pady=4)
        ys = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        xs = ttk.Scrollbar(self, orient="horizontal", command=self.text.xview)
        self.text.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        self.text.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.text.tag_configure("error", foreground="#b00020")
        self.text.tag_configure("warn", foreground="#a15c00")
        self.text.tag_configure("ok", foreground="#1b6e20")
        self.text.tag_configure("trace", foreground="#777777")

    def log(self, message: str, level: str = "info") -> None:
        stamp = time.strftime("%H:%M:%S")
        self.text.configure(state="normal")
        for line in message.splitlines() or [""]:
            self.text.insert("end", f"{stamp}  {line}\n", (level,))
        lines = int(self.text.index("end-1c").split(".")[0])
        if lines > self.MAX_LINES:
            self.text.delete("1.0", f"{lines - self.MAX_LINES}.0")
        self.text.configure(state="disabled")
        self.text.see("end")

    def clear(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")

    def get_text(self) -> str:
        return self.text.get("1.0", "end-1c")
