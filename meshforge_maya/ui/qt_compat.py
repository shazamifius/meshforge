"""Qt Compatibility layer for PySide6 (Maya 2025+) and PySide2 (Maya 2020-2024)."""

from __future__ import annotations
import sys

try:
    from PySide6 import QtWidgets, QtCore, QtGui
    IS_PYSIDE6 = True
    IS_PYSIDE2 = False
except ImportError:
    try:
        from PySide2 import QtWidgets, QtCore, QtGui
        IS_PYSIDE6 = False
        IS_PYSIDE2 = True
    except ImportError:
        raise ImportError("MeshForge Maya requires PySide6 or PySide2.")

# Qt aliases
Signal = QtCore.Signal
Slot = QtCore.Slot
Property = QtCore.Property

__all__ = ["QtWidgets", "QtCore", "QtGui", "Signal", "Slot", "Property", "IS_PYSIDE6", "IS_PYSIDE2"]
