"""Small modal dialogs."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional


class PortOptionsDialog(tk.Toplevel):
    """Serial line options (stop bits, RTS/DTR, timeout)."""

    def __init__(self, parent: tk.Misc, options: dict):
        super().__init__(parent)
        self.title("Port Options")
        self.transient(parent.winfo_toplevel())
        self.resizable(False, False)
        self.result: Optional[dict] = None

        body = ttk.Frame(self, padding=14)
        body.pack(fill="both", expand=True)
        self.stopbits = tk.IntVar(value=options.get("stopbits", 2))
        self.rts = tk.BooleanVar(value=options.get("rts", True))
        self.dtr = tk.BooleanVar(value=options.get("dtr", False))
        self.timeout = tk.DoubleVar(value=options.get("timeout", 1.0))

        ttk.Label(body, text="Stop bits:").grid(row=0, column=0, sticky="w", pady=3)
        sb = ttk.Frame(body)
        sb.grid(row=0, column=1, sticky="w")
        ttk.Radiobutton(sb, text="1", value=1, variable=self.stopbits).pack(side="left")
        ttk.Radiobutton(sb, text="2", value=2, variable=self.stopbits).pack(side="left", padx=(8, 0))

        ttk.Checkbutton(body, text="Assert RTS (needed when menu 05-08 CAT RTS = ENABLE)",
                        variable=self.rts).grid(row=1, column=0, columnspan=2, sticky="w", pady=3)
        ttk.Checkbutton(body, text="Assert DTR (normally off - DTR can key PTT/CW)",
                        variable=self.dtr).grid(row=2, column=0, columnspan=2, sticky="w", pady=3)

        ttk.Label(body, text="Answer timeout (s):").grid(row=3, column=0, sticky="w", pady=3)
        ttk.Spinbox(body, from_=0.2, to=5.0, increment=0.1, textvariable=self.timeout,
                    width=6).grid(row=3, column=1, sticky="w")

        hint = ("Data format is fixed at 8 data bits, no parity.\n"
                "Use the radio's \"Enhanced COM Port\" for CAT; the \"Standard\" port is for PTT/keying.")
        ttk.Label(body, text=hint, foreground="#505050", justify="left").grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(10, 0))

        buttons = ttk.Frame(body)
        buttons.grid(row=5, column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(buttons, text="OK", command=self._ok, default="active").pack(side="left", padx=4)
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="left")

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set()
        self.wait_visibility()
        self.focus_set()

    def _ok(self) -> None:
        try:
            timeout = float(self.timeout.get())
        except (tk.TclError, ValueError):
            timeout = 1.0
        self.result = {
            "stopbits": int(self.stopbits.get()),
            "rts": bool(self.rts.get()),
            "dtr": bool(self.dtr.get()),
            "timeout": min(5.0, max(0.2, timeout)),
        }
        self.destroy()


class TextDialog(tk.Toplevel):
    """Read-only scrollable text (used for operation reports)."""

    def __init__(self, parent: tk.Misc, title: str, text: str):
        super().__init__(parent)
        self.title(title)
        self.transient(parent.winfo_toplevel())
        frame = ttk.Frame(self, padding=10)
        frame.pack(fill="both", expand=True)
        txt = tk.Text(frame, wrap="word", width=90, height=20, font=("Consolas", 9))
        ys = ttk.Scrollbar(frame, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=ys.set)
        txt.insert("1.0", text)
        txt.configure(state="disabled")
        txt.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        ttk.Button(frame, text="Close", command=self.destroy).grid(row=1, column=0, columnspan=2,
                                                                  sticky="e", pady=(8, 0))
        self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set()
