import os
import tkinter.ttk as ttk

"""
Prosty system motywów dla aplikacji.
Można przełączać między 'dark' i 'light' za pomocą set_theme().
"""

COLOR_SCHEMES = {
    "dark": {
        "bg": "#1e293b",
        "card_bg": "#273449",
        "accent": "#3b82f6",
        "accent_hover": "#2563eb",
        "text": "#f1f5f9",
        "muted": "#cbd5e1",
        "border": "#334155",
        "input_bg": "#1f2937",
        "input_border": "#3b475c",
    },
    "light": {
        "bg": "#E9ECEF",
        "card_bg": "#F8FAFC",
        "border": "#CBD5E1",
        "text": "#0F172A",
        "muted": "#475569",
        "accent": "#2563EB",
        "accent_hover": "#1D4ED8",
        "input_bg": "#FFFFFF",
        "input_border": "#CBD5E1",
    },
}

# plik z zapamiętanym motywem (obok theme.py)
_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "theme_config.txt")

# domyślnie jasny, ale spróbujemy wczytać z pliku
CURRENT_THEME = "light"
try:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        mode = f.read().strip()
        if mode in COLOR_SCHEMES:
            CURRENT_THEME = mode
except OSError:
    # brak pliku / błąd odczytu – zostaje "light"
    pass


def set_theme(mode: str) -> None:
    """Ustaw aktualny motyw ('dark' lub 'light') i zapisz do pliku."""
    global CURRENT_THEME

    if mode in COLOR_SCHEMES and mode != CURRENT_THEME:
        CURRENT_THEME = mode
        try:
            with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
                f.write(CURRENT_THEME)
        except OSError:
            # jeśli nie da się zapisać – trudno, po prostu nie zapamięta
            pass


def get_theme() -> str:
    """Zwróć nazwę aktualnego motywu ('dark' lub 'light')."""
    return CURRENT_THEME


def get_colors() -> dict:
    """Zwraca słownik kolorów dla aktualnego motywu."""
    return COLOR_SCHEMES[CURRENT_THEME]


def apply_entry_style(root) -> None:
    """
    Zastosuj spójny styl dla pól tekstowych (Entry) w całej aplikacji.

    Uwaga: styl ma nazwę 'Dark.TEntry' ze względów zgodności z resztą kodu –
    jest używany zarówno w trybie jasnym, jak i ciemnym.
    """
    colors = get_colors()
    style = ttk.Style(root)

    style.configure(
        "Dark.TEntry",
        fieldbackground=colors["input_bg"],
        background=colors["input_bg"],  # ważne na Windowsie
        foreground=colors["text"],
        bordercolor=colors["border"],
        lightcolor=colors["border"],
        darkcolor=colors["border"],
        borderwidth=1,
        relief="solid",
    )
