"""Deterministic prek checkers enforcing the ac-django testing conventions.

Each checker is a high-precision, low-false-positive scan over test/source
files. Tolerated paths are supplied from the consuming repo via the hook's
``args`` (inline ``--allow`` globs and/or a ``--baseline`` path-list file); with
no tolerance configured the checkers are strict (zero violations tolerated).
"""
