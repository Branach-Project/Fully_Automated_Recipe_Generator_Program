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

    # Check for kitted ladder in product_display_name or bom_name and swap parent MO if needed
    def get_ladder_size(item_str):
        import re
        match = re.search(r'(\d+\.\d+)', item_str)
        return match.group(1) if match else None

    # If kitted ladder, swap parent MO
    if "kit" in product_display_name.lower() or "kit" in bom_name.lower():
        size = get_ladder_size(product_display_name)
        mo_map = {
            "3.9": "BM/MO/2511385-025",
            "5.1": "BM/MO/2511386-008",
            "6.3": "BM/MO/2510362-001",
            "8.7": "BM/MO/2508284-001",
            "9.6": "Brana/MO/00071", #"BM/MO/2509523-005",
        }
        if size in mo_map:
            _log(f"Detected kitted ladder ({size}m), swapping parent MO to {mo_map[size]}")
            # Re-call database with new parent MO
            component_list, bom_name, product_display_name, child_detail = database.calling_database(
                mo_map[size], child_mo
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
        self._last_thread = None
        self._timeout_timer = None
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

        # Barcode scan logic: after scanning parent, focus child; after child, auto-run if valid
        def on_parent_enter(event=None):
            self.parent_var.set(parent_entry.get().strip())
            child_entry.focus_set()
            self.status_var.set("Parent MO scanned. Please scan Child MO.")

        def on_child_enter(event=None):
            self.child_var.set(child_entry.get().strip())
            parent = self.parent_var.get().strip()
            child = self.child_var.get().strip()
            # Removed check that prevented parent and child MO from being the same
            self.status_var.set("Script loaded. Running recipe...")
            self.run_button.focus_set()
            self._handle_run()  # Automatically run recipe after child MO is scanned

        parent_entry.bind("<Return>", on_parent_enter)
        child_entry.bind("<Return>", on_child_enter)

        # Sample buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, sticky="ew", pady=(0, 8))
        sample_fly_btn = ttk.Button(button_frame, text="Sample Fly", command=self._sample_fly)
        sample_fly_btn.pack(side="left", padx=(0, 8))

        self.run_button = ttk.Button(main_frame, text="Run Recipe", command=self._handle_run)
        self.run_button.grid(row=5, column=0, sticky="ew")


        # Last run time label
        self._last_run_time = None
        self._last_run_label_var = tk.StringVar()
        self._last_run_label_var.set("")
        last_run_label = ttk.Label(main_frame, textvariable=self._last_run_label_var, foreground="blue")
        last_run_label.grid(row=6, column=0, sticky="ew", pady=(0, 4))
        self._update_last_run_label()

        self.log_output = ScrolledText(main_frame, height=15, width=60, state="disabled")
        self.log_output.grid(row=7, column=0, pady=(12, 0), sticky="nsew")

        # Configure tags for colored output
        self.log_output.tag_configure("success", foreground="green")
        self.log_output.tag_configure("fail", foreground="red")

        main_frame.rowconfigure(7, weight=1)
        main_frame.columnconfigure(0, weight=1)

    def _sample_fly(self):
        self.parent_var.set("BM/MO/06207-001")
        self.child_var.set("F")

    def _sample_base(self):
        # For now, do nothing (leave blank)
        pass

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
        if "Run completed successfully" in message:
            self.log_output.insert("end", message + "\n", "success")
        elif "fail" in message.lower():
            self.log_output.insert("end", message + "\n", "fail")
        else:
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
        # Removed check that prevented parent and child MO from being the same

        if self._is_running:
            return

        # Clear the log output text box before each run
        self.log_output.configure(state="normal")
        self.log_output.delete("1.0", "end")
        self.log_output.configure(state="disabled")

        self._is_running = True
        self.run_button.configure(state="disabled")
        self._enqueue_log("Starting run...")

        # Record the last run time
        import time
        self._last_run_time = time.time()
        self._update_last_run_label()

        # Start the background thread
        thread = threading.Thread(
            target=self._run_in_background,
            args=(parent_mo, child_mo),
            daemon=True,
        )
        self._last_thread = thread
        thread.start()

        # Start the timeout timer (20 seconds)
        self._timeout_timer = self.root.after(20000, self._timeout_check)

    def _run_in_background(self, parent_mo: str, child_mo: str) -> None:
        try:
            result = run_recipe_once(parent_mo, child_mo, log_fn=self._enqueue_log)
            self._enqueue_log(f"Run completed successfully. Result: {result}")
        except Exception as exc:  # pragma: no cover - surfaced to operators instead
            self._enqueue_log(f"Error: {exc}")
        finally:
            self._log_queue.put("__DONE__")
            # Cancel the timeout timer if still running
            if self._timeout_timer is not None:
                self.root.after_cancel(self._timeout_timer)
                self._timeout_timer = None

    def _timeout_check(self):
        if self._is_running:
            self._enqueue_log("Run failed (timeout)")
            self._log_queue.put("__DONE__")
            self._is_running = False
            self.run_button.configure(state="normal")
            self._timeout_timer = None

    def _update_last_run_label(self):
        import time
        if self._last_run_time is None:
            self._last_run_label_var.set("")
        else:
            elapsed = int(time.time() - self._last_run_time)
            if elapsed < 60:
                self._last_run_label_var.set(f"Last run: {elapsed} seconds ago")
            elif elapsed < 600:
                mins = elapsed // 60
                secs = elapsed % 60
                self._last_run_label_var.set(f"Last run: {mins} min {secs} sec ago")
            else:
                self._last_run_label_var.set("Last run: 10min+")
        self.root.after(1000, self._update_last_run_label)

    def run(self) -> None:
        self.root.mainloop()


def launch_gui() -> None:
    app = RecipeGeneratorApp()
    app.run()


if __name__ == "__main__":
    launch_gui()