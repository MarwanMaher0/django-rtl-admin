"""Alias for the ``reset_demo`` management command."""

from __future__ import annotations

from .reset_demo import Command as ResetDemoCommand


class Command(ResetDemoCommand):
    help = ResetDemoCommand.help
