"""Main window for the Solar Panel Performance Monitor (v5).

Tkinter-only GUI. One background worker thread (recorder) does all sensor
I/O; this module never calls Tk from that thread. Samples flow through a
queue.Queue and the GUI drains it with after().
"""

from __future__ import annotations

import argparse
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from recorder import Recorder, SessionConfig
from recorder import (
    STATUS_MONITORING,
    STATUS_STOPPED,
    STATUS_COMPLETED,
    STATUS_ERROR,
)
from sensor import make_sensor


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Solar Panel Performance Monitor"
    )
    parser.add_argument(
        "--duration", type=float, default=600.0,
        help="Session duration in seconds (default: 600)",
    )
    parser.add_argument(
        "--interval", type=float, default=1.0,
        help="Sampling interval in seconds (default: 1.0)",
    )
    return parser.parse_args()


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Solar Panel Performance Monitor")
        self.root.resizable(False, False)

        self.recorder = Recorder(SessionConfig())
        self._poll_job = None
        self._mode_var = tk.StringVar(value="hardware")

        self._build_ui()
        self._update_banner()
        self._poll_queue()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._update_ui_state()

    # ------------------------------------------------------------------ #
    # UI construction
    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        pad = {"padx": 10, "pady": 6}
        frame = ttk.Frame(self.root)
        frame.pack(fill="both", expand=True)

        # --- Mode selection (radio buttons, no dropdown) -----------------
        mode_frame = ttk.LabelFrame(frame, text="Mode", padding=8)
        mode_frame.pack(fill="x", **pad)
        self._rb_hw = ttk.Radiobutton(
            mode_frame, text="Hardware", variable=self._mode_var,
            value="hardware", command=self._on_mode_change,
        )
        self._rb_sim = ttk.Radiobutton(
            mode_frame, text="Simulation", variable=self._mode_var,
            value="simulation", command=self._on_mode_change,
        )
        self._rb_hw.pack(side="left")
        self._rb_sim.pack(side="left", padx=(20, 0))

        # --- Simulation banner (red) ------------------------------------
        self._banner = tk.Label(
            frame,
            text="SIMULATION — NOT REAL DATA",
            fg="white", bg="#c0392b", font=("TkDefaultFont", 10, "bold"),
        )

        # --- Live readings ----------------------------------------------
        read_frame = ttk.LabelFrame(frame, text="Live readings", padding=8)
        read_frame.pack(fill="x", **pad)
        self._v_var = tk.StringVar(value="— V")
        self._i_var = tk.StringVar(value="— mA")
        self._p_var = tk.StringVar(value="— W")
        ttk.Label(read_frame, text="Voltage:").grid(row=0, column=0, sticky="w")
        ttk.Label(read_frame, textvariable=self._v_var).grid(
            row=0, column=1, sticky="w", padx=(8, 0)
        )
        ttk.Label(read_frame, text="Current:").grid(row=1, column=0, sticky="w")
        ttk.Label(read_frame, textvariable=self._i_var).grid(
            row=1, column=1, sticky="w", padx=(8, 0)
        )
        ttk.Label(read_frame, text="Power:").grid(row=2, column=0, sticky="w")
        ttk.Label(read_frame, textvariable=self._p_var).grid(
            row=2, column=1, sticky="w", padx=(8, 0)
        )

        # --- Status line -------------------------------------------------
        self._status_var = tk.StringVar(value="Ready")
        ttk.Label(frame, textvariable=self._status_var, anchor="w").pack(
            fill="x", **pad
        )

        # --- Buttons -----------------------------------------------------
        btn_frame = ttk.Frame(frame, padding=8)
        btn_frame.pack(fill="x")
        self._btn_start = ttk.Button(btn_frame, text="Start", command=self._on_start)
        self._btn_stop = ttk.Button(btn_frame, text="Stop", command=self._on_stop)
        self._btn_export = ttk.Button(
            btn_frame, text="Export CSV", command=self._on_export
        )
        self._btn_start.pack(side="left")
        self._btn_stop.pack(side="left", padx=(8, 0))
        self._btn_export.pack(side="left", padx=(8, 0))

    # ------------------------------------------------------------------ #
    # Mode / banner
    # ------------------------------------------------------------------ #
    def _on_mode_change(self) -> None:
        self._update_banner()
        self._update_ui_state()

    def _update_banner(self) -> None:
        sim = self._mode_var.get() == "simulation"
        if sim:
            self._banner.pack(fill="x", padx=10, pady=(0, 6))
        else:
            self._banner.pack_forget()

    # ------------------------------------------------------------------ #
    # UI state + status line
    # ------------------------------------------------------------------ #
    def _update_ui_state(self) -> None:
        monitoring = self.recorder.is_monitoring()
        state = ["disabled"] if monitoring else ["!disabled"]
        self._rb_hw.state(state)
        self._rb_sim.state(state)
        self._btn_start.state(state)

        self._btn_stop.state(["!disabled"] if monitoring else ["disabled"])

        summary = self.recorder.summary()
        can_export = (
            summary["status"] in (STATUS_STOPPED, STATUS_COMPLETED)
            and summary["samples_recorded"] > 0
        )
        self._btn_export.state(["!disabled"] if can_export else ["disabled"])

        self._refresh_status_line(summary)

    def _refresh_status_line(self, summary: dict) -> None:
        parts = [summary["status"]]
        if summary["error_message"]:
            parts.append(f"— {summary['error_message']}")
        if summary["status"] == STATUS_MONITORING:
            parts.append(f"time remaining {self._mmss(summary['time_remaining_s'])}")
        parts.append(f"samples {summary['samples_recorded']}")
        self._status_var.set("  |  ".join(parts))

    @staticmethod
    def _mmss(seconds: float) -> str:
        seconds = max(0, int(seconds))
        return f"{seconds // 60:02d}:{seconds % 60:02d}"

    # ------------------------------------------------------------------ #
    # Queue polling (main thread only)
    # ------------------------------------------------------------------ #
    def _poll_queue(self) -> None:
        for sample in self.recorder.drain_queue():
            self._apply_sample(sample)
        self._update_ui_state()
        self._poll_job = self.root.after(200, self._poll_queue)

    def _apply_sample(self, sample: dict) -> None:
        if sample.get("status") == "ok":
            self._v_var.set(f"{sample['voltage_v']:.3f} V")
            self._i_var.set(f"{sample['current_ma']:.1f} mA")
            self._p_var.set(f"{sample['power_w']:.3f} W")
        else:
            self._v_var.set("— V")
            self._i_var.set("— mA")
            self._p_var.set("— W")

    # ------------------------------------------------------------------ #
    # Actions
    # ------------------------------------------------------------------ #
    def _on_start(self) -> None:
        if self.recorder.has_unexported_data():
            if not messagebox.askyesno(
                "Discard unexported data?",
                "The previous session has unexported data. "
                "Start a new session and discard it?",
            ):
                return
        mode = self._mode_var.get()
        try:
            sensor = make_sensor(mode)
        except Exception as exc:  # pragma: no cover - defensive
            messagebox.showerror("Error", f"Cannot create sensor: {exc}")
            return
        try:
            self.recorder.start(sensor)
        except RuntimeError as exc:
            messagebox.showerror("Sensor not found", str(exc))
            return
        self._update_banner()
        self._update_ui_state()

    def _on_stop(self) -> None:
        self.recorder.stop()
        self._update_ui_state()

    def _on_export(self) -> None:
        summary = self.recorder.summary()
        if summary["status"] not in (STATUS_STOPPED, STATUS_COMPLETED):
            return
        if summary["samples_recorded"] == 0:
            return
        from datetime import datetime

        default_name = f"solar_readings_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv"
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile=default_name,
            filetypes=[("CSV files", "*.csv")],
        )
        if not path:
            return
        try:
            count = self.recorder.export_csv(path)
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))
            return
        messagebox.showinfo(
            "Export complete", f"Saved {count} rows to:\n{path}"
        )
        self._update_ui_state()

    def _on_close(self) -> None:
        if self.recorder.has_unexported_data():
            if not messagebox.askyesno(
                "Unsaved data",
                "The session has unexported data. Quit and discard it?",
            ):
                return
        self.recorder.close()
        if self._poll_job is not None:
            try:
                self.root.after_cancel(self._poll_job)
            except Exception:
                pass
        self.root.destroy()


def main() -> None:
    args = parse_args()
    root = tk.Tk()
    app = App(root)
    app.recorder.config.duration_s = float(args.duration)
    app.recorder.config.interval_s = float(args.interval)
    root.mainloop()


if __name__ == "__main__":
    main()
