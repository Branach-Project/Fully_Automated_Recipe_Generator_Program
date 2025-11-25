from __future__ import annotations

import platform
import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Callable, Optional

from bay_allocation import BayAllocation
from database_BOM import Database
from formatting import Formatting
from recipe_generator import RecipeGenerator


LogFn = Optional[Callable[[str], None]]


def run_recipe_once(parent_mo: str, child_mo: str, log_fn: LogFn = None) -> str:
    """Execute a single recipe generation run using the provided MO values."""

    if not parent_mo:
        raise ValueError("Parent MO is required.")
    if not child_mo:
        raise ValueError("Child MO (or B/F) is required.")

    def _log(message: str) -> None:
        if log_fn:
            log_fn(message)
        print(message)

    _log(f"Starting recipe generation for parent '{parent_mo}' and child '{child_mo}'.")

    database = Database()
    formatting = Formatting()
    generator = RecipeGenerator()
    bay_allocation = BayAllocation()

    component_list, bom_name, product_display_name, child_detail = database.calling_database(
        parent_mo, child_mo
    )

    _log(f"Fetched {len(component_list)} components for {product_display_name}.")

    formatted_components = formatting.format(str(component_list))
    _log("Components formatted. Running generator...")

    execute_fly_or_base = generator.run(formatted_components, product_display_name, child_detail)
    _log(f"Recipe generator completed with result: {execute_fly_or_base}.")

    # Placeholder for future use. Keeping instantiation above ensures internal setup remains intact.
    _log("Bay allocation step skipped (not in use).")

    return execute_fly_or_base


class RecipeGeneratorApp:
    """Minimal Tkinter UI so operators can trigger recipe runs without the console."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Recipe Generator")

        self.parent_var = tk.StringVar()
        self.child_var = tk.StringVar()

        self._build_ui()

        self._log_queue: queue.Queue[str] = queue.Queue()
        self._is_running = False
        arch = " ".join(filter(None, platform.architecture()))
        self._enqueue_log(f"Detected platform: {arch}")
        self._poll_queue()

    def _build_ui(self) -> None:
        main_frame = ttk.Frame(self.root, padding=16)
        main_frame.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        ttk.Label(main_frame, text="Parent MO").grid(row=0, column=0, sticky="w")
        parent_entry = ttk.Entry(main_frame, textvariable=self.parent_var, width=30)
        parent_entry.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        parent_entry.focus()

        ttk.Label(main_frame, text="Child MO (or B/F)").grid(row=2, column=0, sticky="w")
        child_entry = ttk.Entry(main_frame, textvariable=self.child_var, width=30)
        child_entry.grid(row=3, column=0, sticky="ew", pady=(0, 8))

        self.run_button = ttk.Button(main_frame, text="Run Recipe", command=self._handle_run)
        self.run_button.grid(row=4, column=0, sticky="ew")

        self.log_output = ScrolledText(main_frame, height=15, width=60, state="disabled")
        self.log_output.grid(row=5, column=0, pady=(12, 0), sticky="nsew")

        main_frame.rowconfigure(5, weight=1)
        main_frame.columnconfigure(0, weight=1)

    def _enqueue_log(self, message: str) -> None:
        self._log_queue.put(message)

    def _poll_queue(self) -> None:
        try:
            while True:
                message = self._log_queue.get_nowait()
                if message == "__DONE__":
                    self._is_running = False
                    self.run_button.configure(state="normal")
                else:
                    self._append_log(message)
        except queue.Empty:
            pass

        self.root.after(100, self._poll_queue)

    def _append_log(self, message: str) -> None:
        self.log_output.configure(state="normal")
        self.log_output.insert("end", message + "\n")
        self.log_output.see("end")
        self.log_output.configure(state="disabled")

    def _handle_run(self) -> None:
        parent_mo = self.parent_var.get().strip()
        child_mo = self.child_var.get().strip()

        if not parent_mo:
            messagebox.showwarning("Missing Parent MO", "Please enter the parent manufacturing order.")
            return
        if not child_mo:
            messagebox.showwarning("Missing Child MO", "Please enter the child manufacturing order or B/F.")
            return

        if self._is_running:
            return

        self._is_running = True
        self.run_button.configure(state="disabled")
        self._enqueue_log("Starting run...")

        thread = threading.Thread(
            target=self._run_in_background,
            args=(parent_mo, child_mo),
            daemon=True,
        )
        thread.start()

    def _run_in_background(self, parent_mo: str, child_mo: str) -> None:
        try:
            result = run_recipe_once(parent_mo, child_mo, log_fn=self._enqueue_log)
            self._enqueue_log(f"Run completed successfully. Result: {result}")
        except Exception as exc:  # pragma: no cover - surfaced to operators instead
            self._enqueue_log(f"Error: {exc}")
        finally:
            self._log_queue.put("__DONE__")

    def run(self) -> None:
        self.root.mainloop()


def launch_gui() -> None:
    app = RecipeGeneratorApp()
    app.run()


if __name__ == "__main__":
    launch_gui()