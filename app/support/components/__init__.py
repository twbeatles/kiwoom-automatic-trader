"""Reusable Fluent-style components on pure PyQt6 (no new dependency).

srtgo(ktrain) patterns borrowed per DESKTOP_UI_DESIGN_RULES §27:
section title + secondary text, empty states, status badges, non-modal
InfoBar host. All spacing comes from design_tokens; colors come from the
central theme via dynamic properties (no per-page hex, §7/§9).
"""

from __future__ import annotations
