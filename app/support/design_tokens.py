"""Desktop design tokens (DESKTOP_UI_DESIGN_RULES §§5-7).

Qt-free pure constants + tiny helpers so unit tests run without PyQt6.
Layout/spacing/typography live here; semantic color *keys* map onto the
existing ``app.support.theme.TOKENS`` palettes (no second color system).

srtgo(ktrain)借用: compact desktop density, 24px page margin / 24px
section gap, single accent per screen, title+secondary text pattern.
"""

from __future__ import annotations

# §5 spacing scale (only these values in layout code)
SPACE_XXS = 4
SPACE_XS = 8
SPACE_SM = 12
SPACE_MD = 16
SPACE_LG = 24
SPACE_XL = 32

SPACING_SCALE = (SPACE_XXS, SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG, SPACE_XL)

# Control heights (§5 example)
CONTROL_HEIGHT_SM = 32
CONTROL_HEIGHT_MD = 36
CONTROL_HEIGHT_LG = 40

# Page / section geometry
PAGE_MARGIN = 24
SECTION_GAP = 24
GROUP_GAP = 16
FORM_ROW_GAP = 12
CARD_RADIUS = 8

# §6 typography roles (px design units at scale 1.0; theme converts to pt)
TYPE_PAGE_TITLE = 22
TYPE_SECTION_TITLE = 16
TYPE_BODY = 14
TYPE_SECONDARY = 12
TYPE_CAPTION = 11

TYPOGRAPHY_ROLES = {
    "page_title": TYPE_PAGE_TITLE,
    "section_title": TYPE_SECTION_TITLE,
    "body": TYPE_BODY,
    "secondary": TYPE_SECONDARY,
    "caption": TYPE_CAPTION,
}

# §7 semantic color keys (must exist in theme.TOKENS[theme]).
SEMANTIC_KEYS = (
    "primary",
    "background",
    "surface",
    "surface_alt",
    "border",
    "text_primary",
    "text_secondary",
    "success",
    "warning",
    "error",
)

# Map semantic keys onto the existing theme token names per theme.
SEMANTIC_MAP = {
    "dark": {
        "primary": "accent_solid",
        "background": "bg",
        "surface": "surface",
        "surface_alt": "surface_2",
        "border": "border",
        "text_primary": "text",
        "text_secondary": "text_muted",
        "success": "success",
        "warning": "warning",
        "error": "danger",
    },
    "light": {
        "primary": "accent_solid",
        "background": "bg",
        "surface": "surface",
        "surface_alt": "surface_2",
        "border": "border",
        "text_primary": "text",
        "text_secondary": "text_muted",
        "success": "success",
        "warning": "warning",
        "error": "danger",
    },
}


def semantic_color(theme: str, key: str) -> str:
    """Return the concrete theme token name for a semantic *key*."""
    mapping = SEMANTIC_MAP.get(theme, SEMANTIC_MAP["dark"])
    return mapping.get(key, key)


def is_spacing(value: int) -> bool:
    """True when *value* belongs to the §5 spacing scale."""
    try:
        return int(value) in SPACING_SCALE
    except (TypeError, ValueError):
        return False
