'''
Stop control for the LinkedIn bot: always-on-top Stop button, Ctrl+Shift+Q,
and PyAutoGUI failsafe (mouse to top-left corner).
'''

from __future__ import annotations

import threading
import time
import tkinter as tk
from tkinter import font as tkfont

_stop_event = threading.Event()
_ui_thread: threading.Thread | None = None
_hotkey_thread: threading.Thread | None = None
_root: tk.Tk | None = None
_started = False


class BotStopped(Exception):
    '''Raised when the user requests a stop via the Stop UI / hotkey / failsafe.'''


def request_stop(reason: str = "user") -> None:
    _stop_event.set()
    try:
        print(f"\n*** STOP REQUESTED ({reason}) - bot will exit shortly ***\n", flush=True)
    except Exception:
        pass


def clear_stop() -> None:
    _stop_event.clear()


def should_stop() -> bool:
    return _stop_event.is_set()


def raise_if_stopped() -> None:
    if should_stop():
        raise BotStopped("Stop requested by user")


def _on_stop_click() -> None:
    request_stop("stop_button")
    global _root
    if _root is not None:
        try:
            _root.after(0, _root.destroy)
        except Exception:
            pass


def _run_ui() -> None:
    global _root
    try:
        root = tk.Tk()
        _root = root
        root.title("Job Bot")
        root.attributes("-topmost", True)
        root.resizable(False, False)
        # Place near top-right
        root.update_idletasks()
        w, h = 200, 90
        sw = root.winfo_screenwidth()
        x = max(0, sw - w - 24)
        root.geometry(f"{w}x{h}+{x}+24")

        title = tk.Label(root, text="LinkedIn Job Bot", font=tkfont.Font(size=9))
        title.pack(pady=(8, 2))
        hint = tk.Label(
            root,
            text="Ctrl+Shift+Q  |  corner failsafe",
            font=tkfont.Font(size=7),
            fg="#555555",
        )
        hint.pack()
        btn = tk.Button(
            root,
            text="STOP BOT",
            fg="white",
            bg="#C62828",
            activebackground="#B71C1C",
            activeforeground="white",
            font=tkfont.Font(size=12, weight="bold"),
            command=_on_stop_click,
            height=1,
            width=14,
        )
        btn.pack(pady=6, padx=10, fill="x")
        root.protocol("WM_DELETE_WINDOW", _on_stop_click)
        root.bind("<Escape>", lambda _e: _on_stop_click())
        root.bind("<Control-q>", lambda _e: _on_stop_click())

        while not should_stop():
            try:
                root.update()
            except tk.TclError:
                break
            time.sleep(0.05)
        try:
            root.destroy()
        except Exception:
            pass
    except Exception as e:
        print(f"Stop UI failed to start: {e}", flush=True)
    finally:
        _root = None


def _run_hotkey_watcher() -> None:
    '''Global Ctrl+Shift+Q via Win32 GetAsyncKeyState (no extra deps).'''
    try:
        import ctypes
    except Exception:
        return
    user32 = ctypes.windll.user32
    VK_CONTROL, VK_SHIFT, VK_Q = 0x11, 0x10, 0x51
    armed = True
    while not should_stop():
        try:
            ctrl = user32.GetAsyncKeyState(VK_CONTROL) & 0x8000
            shift = user32.GetAsyncKeyState(VK_SHIFT) & 0x8000
            q = user32.GetAsyncKeyState(VK_Q) & 0x8000
            if ctrl and shift and q:
                if armed:
                    request_stop("hotkey_ctrl_shift_q")
                    break
            else:
                armed = True
        except Exception:
            break
        time.sleep(0.12)


def start_stop_controls() -> None:
    '''Start always-on-top Stop button + global hotkey watcher (once).'''
    global _ui_thread, _hotkey_thread, _started
    if _started:
        return
    _started = True
    clear_stop()
    _ui_thread = threading.Thread(target=_run_ui, name="bot-stop-ui", daemon=True)
    _ui_thread.start()
    _hotkey_thread = threading.Thread(
        target=_run_hotkey_watcher, name="bot-stop-hotkey", daemon=True
    )
    _hotkey_thread.start()
    print(
        "Stop controls ready: [STOP BOT] window | Ctrl+Shift+Q | mouse to top-left corner",
        flush=True,
    )


def stop_stop_controls() -> None:
    request_stop("shutdown")
    global _root
    if _root is not None:
        try:
            _root.after(0, _root.destroy)
        except Exception:
            pass
