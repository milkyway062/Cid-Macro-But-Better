import tkinter as tk
import threading
import time
import logging
import queue
import sys
import os
import json
import keyboard
import ctypes

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)
sys.path.insert(0, os.path.join(_here, "core"))
import Main
import state
import softlocks

_APPDATA = os.environ.get("APPDATA", os.path.expanduser("~"))
_CONFIG_DIR = os.path.join(_APPDATA, "CidMacro")
os.makedirs(_CONFIG_DIR, exist_ok=True)
CONFIG_PATH = os.path.join(_CONFIG_DIR, "config.json")

def _load_config() -> dict:
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def _save_config(data: dict):
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

# ── Palette ───────────────────────────────────────────────────
BG      = "#1e1e1e"
SURFACE = "#2b2b2b"
ENTRY   = "#3a3a3a"
FG      = "#e0e0e0"
FG_DIM  = "#888888"
SEL_BG  = "#404040"
GREEN   = "#4CAF50";  GREEN_A = "#388E3C"
RED     = "#f44336";  RED_A   = "#c62828"
ERR_BG  = "#5a1a1a"
INDIGO  = "#5c6bc0";  INDIGO_A = "#3949ab"


class _QueueHandler(logging.Handler):
    def __init__(self, q):
        super().__init__()
        self.log_queue = q

    def emit(self, record):
        try:
            self.log_queue.put_nowait(self.format(record))
        except queue.Full:
            pass


class MacroGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Cid Macro")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)

        self._log_queue: queue.Queue = queue.Queue(maxsize=500)
        self._stopping = False
        self._cfg = _load_config()

        self._attach_log_handler()
        self._build_ui()
        self._apply_config()
        self._tick()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        keyboard.on_press_key("f1", lambda _: self.root.after(0, self._on_start))
        keyboard.on_press_key("f3", lambda _: self.root.after(0, self._on_stop))

    # ── Helpers ───────────────────────────────────────────────
    def _lbl(self, parent, text="", textvariable=None, fg=FG, anchor="w", **kw):
        cfg = dict(bg=BG, fg=fg, anchor=anchor, **kw)
        if textvariable:
            cfg["textvariable"] = textvariable
        else:
            cfg["text"] = text
        return tk.Label(parent, **cfg)

    def _entry(self, parent, textvariable, width):
        return tk.Entry(
            parent, textvariable=textvariable, width=width,
            bg=ENTRY, fg=FG, insertbackground=FG,
            selectbackground=SEL_BG, selectforeground=FG,
            relief="flat", bd=4,
        )

    def _sep(self, row):
        tk.Frame(self.root, bg="#3a3a3a", height=1).grid(
            row=row, column=0, columnspan=6, sticky="ew", padx=8, pady=3
        )

    def _chk(self, parent, text, variable, command=None):
        return tk.Checkbutton(
            parent, text=text, variable=variable, command=command,
            bg=BG, fg=FG, selectcolor=ENTRY,
            activebackground=BG, activeforeground=FG,
            bd=0, cursor="hand2",
        )

    def _attach_log_handler(self):
        h = _QueueHandler(self._log_queue)
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
        logging.getLogger().addHandler(h)

    # ── UI construction ───────────────────────────────────────
    def _build_ui(self):
        p  = {"padx": 8,  "pady": 4}
        ps = {"padx": 8,  "pady": 2}   # tight spacing
        ph = {"padx": 8,  "pady": 6}   # heading/button rows

        # ── Row 0: Start / Stop / Status / Hotkeys ──
        self._start_btn = tk.Button(
            self.root, text="Start  F1", width=10, command=self._on_start,
            bg=GREEN, fg="white", activebackground=GREEN_A, activeforeground="white",
            relief="flat", bd=0, cursor="hand2",
        )
        self._start_btn.grid(row=0, column=0, **ph)

        self._stop_btn = tk.Button(
            self.root, text="Stop  F3", width=10, command=self._on_stop,
            bg=RED, fg="white", activebackground=RED_A, activeforeground="white",
            relief="flat", bd=0, cursor="hand2", state="disabled",
        )
        self._stop_btn.grid(row=0, column=1, **ph)

        self._status_var = tk.StringVar(value="idle")
        self._lbl(self.root, textvariable=self._status_var, fg=FG_DIM).grid(
            row=0, column=2, columnspan=4, sticky="w", **ph
        )

        # ── Sep ──
        self._sep(1)

        # ── Row 2: Counters ──
        self._runs_var = tk.StringVar(value="Runs: 0")
        self._wins_var = tk.StringVar(value="Wins: 0")
        self._loss_var = tk.StringVar(value="Losses: 0")
        self._lbl(self.root, textvariable=self._runs_var, width=10).grid(row=2, column=0, sticky="w", **p)
        self._lbl(self.root, textvariable=self._wins_var, width=10).grid(row=2, column=1, sticky="w", **p)
        self._lbl(self.root, textvariable=self._loss_var, width=12).grid(row=2, column=2, sticky="w", **p)
        self._lbl(self.root, "F1: Start   F3: Stop", fg=FG_DIM).grid(row=2, column=3, columnspan=3, sticky="e", padx=(0, 8), pady=4)

        # ── Row 3: Timers ──
        self._lbl(self.root, "Session:", fg=FG_DIM).grid(row=3, column=0, sticky="w", **ps)
        self._sess_var = tk.StringVar(value="00:00:00")
        self._lbl(self.root, textvariable=self._sess_var, width=9).grid(row=3, column=1, sticky="w", **ps)

        self._lbl(self.root, "Run:", fg=FG_DIM).grid(row=3, column=2, sticky="w", **ps)
        self._run_time_var = tk.StringVar(value="00:00:00")
        self._run_time_lbl = self._lbl(self.root, textvariable=self._run_time_var, width=9)
        self._run_time_lbl.grid(row=3, column=3, sticky="w", **ps)

        # ── Sep ──
        self._sep(4)

        # ── Row 5: Timeout + Rejoin ──
        self._lbl(self.root, "Timeout (s):", fg=FG_DIM).grid(row=5, column=0, sticky="w", **p)
        self._timeout_var = tk.StringVar(value=str(int(state.RUN_TIMEOUT)))
        self._timeout_entry = self._entry(self.root, self._timeout_var, 6)
        self._timeout_entry.grid(row=5, column=1, sticky="w", **p)
        self._timeout_entry.bind("<Return>", self._apply_timeout)
        self._timeout_entry.bind("<FocusOut>", self._apply_timeout)

        self._lbl(self.root, "Rejoin after:", fg=FG_DIM).grid(row=5, column=2, sticky="w", **p)
        self._rejoin_var = tk.StringVar(value=str(state.AUTO_REJOIN_AFTER_RUNS))
        self._rejoin_entry = self._entry(self.root, self._rejoin_var, 6)
        self._rejoin_entry.grid(row=5, column=3, sticky="w", **p)
        self._rejoin_entry.bind("<Return>", self._apply_rejoin)
        self._rejoin_entry.bind("<FocusOut>", self._apply_rejoin)

        self._lbl(self.root, "runs  (0 = off)", fg=FG_DIM).grid(row=5, column=4, sticky="w", padx=(0, 8), pady=4)

        # ── Row 6: Private server + Join + VC chat ──
        self._lbl(self.root, "Private server link:", fg=FG_DIM).grid(row=6, column=0, sticky="w", **p)
        self._ps_var = tk.StringVar(value=state.PRIVATE_SERVER_CODE)
        self._ps_entry = self._entry(self.root, self._ps_var, 30)
        self._ps_entry.grid(row=6, column=1, columnspan=3, sticky="ew", **p)
        self._ps_entry.bind("<FocusOut>", self._apply_private_server)
        self._ps_entry.bind("<Return>", self._apply_private_server)

        tk.Button(
            self.root, text="Join PS", width=7, command=self._on_join_ps,
            bg=INDIGO, fg="white", activebackground=INDIGO_A, activeforeground="white",
            relief="flat", bd=0, cursor="hand2",
        ).grid(row=6, column=4, sticky="w", **p)

        self._vc_chat_var = tk.BooleanVar(value=state.VC_CHAT)
        self._chk(self.root, "VC chat", self._vc_chat_var, self._apply_vc_chat).grid(
            row=6, column=5, sticky="w", padx=(4, 8), pady=4
        )

        # ── Row 7: Webhook ──
        self._lbl(self.root, "Webhook URL:", fg=FG_DIM).grid(row=7, column=0, sticky="w", **p)
        self._wh_var = tk.StringVar()
        if state.WEBHOOK_URL.startswith("https://"):
            self._wh_var.set(state.WEBHOOK_URL)
        self._wh_entry = self._entry(self.root, self._wh_var, 48)
        self._wh_entry.grid(row=7, column=1, columnspan=5, sticky="ew", **p)
        self._wh_entry.bind("<FocusOut>", lambda _: self._save())
        self._wh_entry.bind("<Return>", lambda _: self._save())

        # ── Sep ──
        self._sep(8)

        # ── Row 9: Log toggle + Update ──
        self._show_log = tk.BooleanVar(value=False)
        self._chk(self.root, "Show log", self._show_log, self._toggle_log).grid(
            row=9, column=0, sticky="w", **p
        )

        self._update_btn = tk.Button(
            self.root, text="Check for Updates", command=self._on_update,
            bg=INDIGO, fg="white", activebackground=INDIGO_A, activeforeground="white",
            relief="flat", bd=0, cursor="hand2",
        )
        self._update_btn.grid(row=9, column=3, columnspan=3, sticky="e", padx=(0, 8), pady=4)

        # ── Row 10: Log panel ──
        self._log_frame = tk.Frame(self.root, bg=SURFACE)
        self._log_frame.grid(row=10, column=0, columnspan=6, sticky="nsew", padx=8, pady=4)
        self._log_frame.grid_remove()

        self._log_text = tk.Text(
            self._log_frame, height=12, width=74, state="disabled",
            wrap="word", font=("Consolas", 9),
            bg=SURFACE, fg=FG_DIM, insertbackground=FG,
            selectbackground=SEL_BG, relief="flat", bd=0,
        )
        _sb = tk.Scrollbar(self._log_frame, command=self._log_text.yview, bg=SURFACE, troughcolor=BG)
        self._log_text.configure(yscrollcommand=_sb.set)
        self._log_text.pack(side="left", fill="both", expand=True)
        _sb.pack(side="right", fill="y")

    # ── Config ────────────────────────────────────────────────
    def _apply_config(self):
        cfg = self._cfg
        if "webhook_url" in cfg:
            self._wh_var.set(cfg["webhook_url"])
            state.WEBHOOK_URL = cfg["webhook_url"]
        if "private_server" in cfg:
            self._ps_var.set(cfg["private_server"])
            state.PRIVATE_SERVER_CODE = cfg["private_server"]
        if "run_timeout" in cfg:
            val = max(10.0, min(600.0, float(cfg["run_timeout"])))
            self._timeout_var.set(str(int(val)))
            state.RUN_TIMEOUT = val
            state.state["run_timeout"] = val
        if "auto_rejoin_runs" in cfg:
            val = max(0, min(1000, int(cfg["auto_rejoin_runs"])))
            self._rejoin_var.set(str(val))
            state.AUTO_REJOIN_AFTER_RUNS = val
        if "vc_chat" in cfg:
            self._vc_chat_var.set(bool(cfg["vc_chat"]))
            state.VC_CHAT = bool(cfg["vc_chat"])

    def _save(self):
        _save_config({
            "webhook_url":      self._wh_var.get().strip(),
            "private_server":   self._ps_var.get().strip(),
            "run_timeout":      self._timeout_var.get().strip(),
            "auto_rejoin_runs": self._rejoin_var.get().strip(),
            "vc_chat":          self._vc_chat_var.get(),
        })

    # ── Callbacks ─────────────────────────────────────────────
    def _on_start(self):
        state.WEBHOOK_URL = self._wh_var.get().strip()
        state.PRIVATE_SERVER_CODE = self._ps_var.get().strip()
        self._save()
        ok = Main.start()
        if ok:
            self._start_btn.config(state="disabled")
            self._stop_btn.config(state="normal")
            self._status_var.set("running")
            self._stopping = False
        else:
            self._status_var.set("error: Roblox not found")

    def _on_stop(self):
        Main.stop()
        state._restart_run.set()
        self._stop_btn.config(state="disabled")
        self._status_var.set("stopping\u2026")
        self._stopping = True

    def _apply_timeout(self, _event=None):
        try:
            val = max(10.0, min(600.0, float(self._timeout_var.get())))
            state.RUN_TIMEOUT = val
            state.state["run_timeout"] = val
            self._timeout_var.set(str(int(val)))
            self._timeout_entry.config(bg=ENTRY)
            self._save()
        except ValueError:
            self._timeout_entry.config(bg=ERR_BG)
            self.root.after(800, lambda: self._timeout_entry.config(bg=ENTRY))
            self._timeout_var.set(str(int(state.RUN_TIMEOUT)))

    def _apply_rejoin(self, _event=None):
        try:
            val = max(0, min(1000, int(self._rejoin_var.get())))
            state.AUTO_REJOIN_AFTER_RUNS = val
            self._rejoin_var.set(str(val))
            self._rejoin_entry.config(bg=ENTRY)
            self._save()
        except ValueError:
            self._rejoin_entry.config(bg=ERR_BG)
            self.root.after(800, lambda: self._rejoin_entry.config(bg=ENTRY))
            self._rejoin_var.set(str(state.AUTO_REJOIN_AFTER_RUNS))

    def _apply_private_server(self, _event=None):
        state.PRIVATE_SERVER_CODE = self._ps_var.get().strip()
        self._ps_entry.config(bg=ENTRY)
        self._save()

    def _apply_vc_chat(self):
        state.VC_CHAT = self._vc_chat_var.get()
        self._save()

    def _on_join_ps(self):
        import subprocess
        code = self._ps_var.get().strip()
        if not code:
            self._status_var.set("no private server link set")
            return
        from helpers import extract_ps_link_code
        url = f"roblox://placeId=16146832113&linkCode={extract_ps_link_code(code)}/"
        try:
            os.startfile(url)
        except Exception:
            try:
                subprocess.Popen(["start", url], shell=True)
            except Exception:
                self._status_var.set("failed to open Roblox")

    # ── Update ────────────────────────────────────────────────
    def _on_update(self):
        self._update_btn.config(state="disabled", text="Checking...")
        self._status_var.set("Checking for updates...")
        threading.Thread(target=self._run_update, daemon=True).start()

    def _run_update(self):
        import hashlib
        import urllib.request

        REPO     = "milkyway062/Cid-Macro-But-Better"
        BASE_API = f"https://api.github.com/repos/{REPO}"
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        SKIP_FILES = {"config.json"}
        SKIP_DIRS  = {"__pycache__", ".git"}

        def git_blob_sha(path):
            try:
                with open(path, "rb") as f:
                    data = f.read()
                return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
            except FileNotFoundError:
                return None

        def fetch(url):
            req = urllib.request.Request(url, headers={"User-Agent": "CidMacro-Updater"})
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.read()

        def set_status(msg):
            self.root.after(0, lambda m=msg: self._status_var.set(m))

        try:
            repo_info = json.loads(fetch(BASE_API))
            branch    = repo_info.get("default_branch", "main")

            set_status("Fetching file list...")
            tree_data = json.loads(fetch(f"{BASE_API}/git/trees/{branch}?recursive=1"))

            to_update = []
            for item in tree_data.get("tree", []):
                if item["type"] != "blob":
                    continue
                path  = item["path"]
                parts = path.replace("\\", "/").split("/")
                if any(p in SKIP_DIRS for p in parts[:-1]):
                    continue
                if parts[-1] in SKIP_FILES:
                    continue
                local_path = os.path.join(BASE_DIR, *parts)
                if git_blob_sha(local_path) != item["sha"]:
                    to_update.append((path, parts))

            if not to_update:
                set_status("Already up to date!")
                self.root.after(3000, lambda: self._status_var.set("idle"))
                return

            for i, (path, parts) in enumerate(to_update):
                set_status(f"Updating {parts[-1]} ({i + 1}/{len(to_update)})...")
                data       = fetch(f"https://raw.githubusercontent.com/{REPO}/{branch}/{path}")
                local_path = os.path.join(BASE_DIR, *parts)
                os.makedirs(os.path.dirname(local_path) or BASE_DIR, exist_ok=True)
                with open(local_path, "wb") as f:
                    f.write(data)

            set_status(f"Updated {len(to_update)} file(s) — restart to apply.")

        except Exception as e:
            set_status(f"Update failed: {e}")
        finally:
            self.root.after(0, lambda: self._update_btn.config(state="normal", text="Check for Updates"))

    def _toggle_log(self):
        if self._show_log.get():
            self._log_frame.grid()
        else:
            self._log_frame.grid_remove()
        self.root.update_idletasks()

    # ── Tick ──────────────────────────────────────────────────
    @staticmethod
    def _fmt(s: float) -> str:
        s = int(max(0, s))
        return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"

    def _tick(self):
        st = state.state
        self._runs_var.set(f"Runs: {st['wins'] + st['losses']}")
        self._wins_var.set(f"Wins: {st['wins']}")
        self._loss_var.set(f"Losses: {st['losses']}")

        if st["session_start"] > 0 and st["running"]:
            self._sess_var.set(self._fmt(time.time() - st["session_start"]))

        if st["running"] and st["run_start"] > 0:
            elapsed = time.time() - st["run_start"]
            self._run_time_var.set(self._fmt(elapsed))
            self._run_time_lbl.config(fg="#ff5555" if elapsed > st["run_timeout"] - 10 else FG)
        elif not st["running"]:
            self._run_time_lbl.config(fg=FG)

        if state._macro_thread and not state._macro_thread.is_alive():
            if self._status_var.get() in ("running", "stopping\u2026"):
                self._start_btn.config(state="normal")
                self._stop_btn.config(state="disabled")
                self._status_var.set("idle")
                self._stopping = False

        if self._show_log.get():
            msgs = []
            try:
                while True:
                    msgs.append(self._log_queue.get_nowait())
            except queue.Empty:
                pass
            if msgs:
                self._log_text.config(state="normal")
                self._log_text.insert("end", "\n".join(msgs) + "\n")
                self._log_text.see("end")
                self._log_text.config(state="disabled")

        self.root.after(500, self._tick)

    # ── Close ─────────────────────────────────────────────────
    def _on_close(self):
        self._save()
        Main.stop()
        if state._macro_thread and state._macro_thread.is_alive():
            state._macro_thread.join(timeout=2.0)
        self.root.destroy()


# ── Single instance guard ─────────────────────────────────────
_MUTEX = None

def _acquire_single_instance():
    global _MUTEX
    _MUTEX = ctypes.windll.kernel32.CreateMutexW(None, True, "CidMacro_SingleInstance")
    return ctypes.windll.kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS


def main():
    if not _acquire_single_instance():
        import tkinter.messagebox as mb
        _r = tk.Tk()
        _r.withdraw()
        mb.showerror(
            "Already running",
            "CidMacro is already running.\n"
            "Open Task Manager → Details → find pythonw.exe → End Task.",
        )
        _r.destroy()
        sys.exit(1)

    threading.Thread(target=softlocks.softlock_watchdog,    daemon=True).start()
    threading.Thread(target=softlocks.global_rejoin_watchdog, daemon=True).start()
    root = tk.Tk()
    MacroGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
