"""Run radio I/O on a background thread and marshal results back to Tk."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from typing import Any, Callable, Optional

ProgressFn = Callable[[int, int, str], None]
JobFn = Callable[[ProgressFn, threading.Event], Any]


class UiDispatcher:
    """Queue callables from any thread; run them on the Tk main loop."""

    def __init__(self, root: tk.Misc, interval_ms: int = 40):
        self.root = root
        self.interval_ms = interval_ms
        self._q: "queue.Queue[tuple[Callable, tuple]]" = queue.Queue()
        self.root.after(self.interval_ms, self._poll)

    def post(self, fn: Callable, *args: Any) -> None:
        self._q.put((fn, args))

    def _poll(self) -> None:
        try:
            for _ in range(500):
                fn, args = self._q.get_nowait()
                try:
                    fn(*args)
                except Exception as exc:  # keep the pump alive
                    self.root.report_callback_exception(type(exc), exc, exc.__traceback__)
        except queue.Empty:
            pass
        self.root.after(self.interval_ms, self._poll)


class BackgroundTask:
    """One radio operation at a time, with progress and cancellation."""

    def __init__(self, dispatcher: UiDispatcher, on_state_change: Callable[[bool], None]):
        self.dispatcher = dispatcher
        self.on_state_change = on_state_change
        self.cancel_event = threading.Event()
        self.busy = False

    def start(
        self,
        job: JobFn,
        on_success: Callable[[Any], None],
        on_error: Callable[[BaseException], None],
        on_progress: Optional[ProgressFn] = None,
    ) -> bool:
        if self.busy:
            return False
        self.busy = True
        self.cancel_event.clear()
        self.on_state_change(True)

        def progress(done: int, total: int, msg: str) -> None:
            if on_progress is not None:
                self.dispatcher.post(on_progress, done, total, msg)

        def run() -> None:
            try:
                result = job(progress, self.cancel_event)
            except BaseException as exc:  # noqa: BLE001 - reported to the UI
                self.dispatcher.post(self._finish, on_error, exc)
            else:
                self.dispatcher.post(self._finish, on_success, result)

        threading.Thread(target=run, name="radio-io", daemon=True).start()
        return True

    def cancel(self) -> None:
        self.cancel_event.set()

    def _finish(self, callback: Callable[[Any], None], arg: Any) -> None:
        self.busy = False
        self.on_state_change(False)
        callback(arg)
