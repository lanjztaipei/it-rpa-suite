"""Shared pytest fixtures for GUI tests.

Maintains a single session-scoped ``tk.Tk`` root interpreter so Windows Tcl/Tk 8.6
never hits ``init.tcl`` re-initialization failures or cross-test ``Variable.__del__``
errors from repeatedly creating and destroying multiple Tk interpreters.
"""

from __future__ import annotations

import gc
import tkinter as tk
from collections.abc import Iterator

import pytest


def _cleanup_children(root: tk.Tk) -> None:
    for child in list(root.winfo_children()):
        try:
            child.destroy()
        except tk.TclError:
            pass


@pytest.fixture(scope="session")
def _session_tk_root() -> Iterator[tk.Tk]:
    root = tk.Tk()
    root.withdraw()
    yield root
    try:
        _cleanup_children(root)
        root.destroy()
    except tk.TclError:
        pass


@pytest.fixture
def tk_root(_session_tk_root: tk.Tk) -> Iterator[tk.Tk]:
    """Provide a clean, withdrawn Tk root reusing the single session interpreter."""
    _cleanup_children(_session_tk_root)
    _session_tk_root.withdraw()
    _session_tk_root.update_idletasks()
    yield _session_tk_root
    _cleanup_children(_session_tk_root)
    _session_tk_root.withdraw()
    _session_tk_root.update_idletasks()
    gc.collect()
