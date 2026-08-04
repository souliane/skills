"""Failures an acroform command can end on, and the exit code each one earns.

A caller that scripts these tools has to be able to tell "your spec is wrong"
from "the PDF did not match what your spec asserted" without reading prose. The
commands raise these; the command body translates them into ``typer.Exit`` so
every entry point in this skill exits the same way.
"""


class AcroformError(Exception):
    """Base class: a failure with a caller-meaningful exit code."""

    exit_code = 1


class SpecError(AcroformError):
    """The JSON spec (or a flag inside it) is malformed — fix the spec, not the PDF."""

    exit_code = 2


class VerificationError(AcroformError):
    """The tool ran; the PDF did not match what the spec asserted."""

    exit_code = 1
