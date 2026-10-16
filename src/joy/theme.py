from dataclasses import dataclass
"""Color system: every color in the app comes from the active palette."""


@dataclass(frozen=True)
class Palette:
    key: str
    name: str
    description: str
    surface: str
    surface_hover: str
    overlay: str
    border: str
    text: str
    text_soft: str
    text_dim: str
    muted: str
    subtle: str
    faint: str
    accent: str
    on_accent: str
    secondary: str
    success: str
    danger: str
    info: str
    code: str
    add_bg: str
    remove_bg: str
    gutter: str

    @property
    def selected(self) -> str:
        return f"bg:{self.accent} {self.on_accent}"

    @property
    def row(self) -> str:
        return f"bg:{self.overlay} {self.text}"

    @property
    def row_strong(self) -> str:
        return f"bg:{self.overlay} bold {self.text}"

    @property
    def row_muted(self) -> str:
        return f"bg:{self.overlay} {self.muted}"

    @property
    def input_box(self) -> str:
        return f"bg:{self.surface} {self.text}"

    @property
    def surface_bg(self) -> str:
        return f"bg:{self.surface}"

    @property
    def overlay_bg(self) -> str:
        return f"bg:{self.overlay}"

    @property
    def strong(self) -> str:
        return f"bold {self.text}"

    @property
    def group(self) -> str:
        return f"bold {self.secondary}"

    @property
    def brand(self) -> str:
        return f"bold {self.info}"

    @property
    def badge_build(self) -> str:
        return f"bg:{self.accent} {self.on_accent} bold"

    @property
    def badge_plan(self) -> str:
        return f"bg:{self.secondary} {self.on_accent} bold"

    @property
    def message(self) -> str:
        return f"{self.text} on {self.surface}"

    @property
    def message_hover(self) -> str:
        return f"{self.text} on {self.surface_hover}"

    @property
    def panel(self) -> str:
        return f"on {self.overlay}"

    @property
    def add_row(self) -> str:
        return f"on {self.add_bg}"

    @property
    def remove_row(self) -> str:
        return f"on {self.remove_bg}"

    @property
    def add_sign(self) -> str:
        return f"bold {self.success}"

    @property
    def remove_sign(self) -> str:
        return f"bold {self.danger}"


PALETTES = {palette.key: palette for palette in (
    Palette(
        "ember", "Ember", "Warm orange accent on neutral greys (the original look)",
        surface="#393939", surface_hover="#4a4a4a", overlay="#1a1a1a", border="#3a3a3a",
        text="#ffffff", text_soft="#d4d4d4", text_dim="#9a9a9a", muted="#808080", subtle="#6b6b6b", faint="#5b6270",
        accent="#e8975a", on_accent="#1a1a1a", secondary="#a78bfa", success="#4ade80", danger="#f87171",
        info="#22d3ee", code="#7ee787", add_bg="#12353a", remove_bg="#3b1b21", gutter="#9ca3af",
    ),
    Palette(
        "moss", "Moss", "Calm green accent with teal highlights",
        surface="#343b36", surface_hover="#434c45", overlay="#161d19", border="#34403a",
        text="#f2f7f3", text_soft="#cfd9d1", text_dim="#9aa89e", muted="#7f8d83", subtle="#69766d", faint="#5a6a60",
        accent="#7ee787", on_accent="#0f1f12", secondary="#5eead4", success="#86efac", danger="#fb7185",
        info="#67e8f9", code="#bef264", add_bg="#12351f", remove_bg="#3b1b24", gutter="#9ca89f",
    ),
    Palette(
        "ocean", "Ocean", "Cool blue accent with soft violet highlights",
        surface="#313a4a", surface_hover="#3f4a5e", overlay="#151b26", border="#2f394a",
        text="#f5f8ff", text_soft="#d3dbe9", text_dim="#9ba7bb", muted="#7f8ba0", subtle="#6a7589", faint="#5b677c",
        accent="#60a5fa", on_accent="#0b1220", secondary="#c4b5fd", success="#4ade80", danger="#f87171",
        info="#38bdf8", code="#7ee787", add_bg="#123a3a", remove_bg="#3b1b2b", gutter="#9aa7bd",
    ),
    Palette(
        "orchid", "Orchid", "Pink accent with warm amber highlights",
        surface="#3a3340", surface_hover="#4b4254", overlay="#1c1720", border="#3b3342",
        text="#fff7fb", text_soft="#e0d3dc", text_dim="#a99aa5", muted="#8c7d88", subtle="#756673", faint="#665a66",
        accent="#f472b6", on_accent="#220f19", secondary="#fbbf24", success="#4ade80", danger="#fb7185",
        info="#f0abfc", code="#7ee787", add_bg="#12353a", remove_bg="#3b1b21", gutter="#a89aa6",
    ),
    Palette(
        "cetak-biru", "Cetak Biru", "Web Maker palette: indigo and turmeric on cool navy",
        surface="#2a3354", surface_hover="#36416a", overlay="#0f1424", border="#28304a",
        text="#e8ecf6", text_soft="#c9d0e4", text_dim="#a6aec4", muted="#8b94ad", subtle="#6b7590", faint="#4f5873",
        accent="#8b9bf0", on_accent="#0f1424", secondary="#e8a33d", success="#7fd8ae", danger="#f2a596",
        info="#a5b2f5", code="#7dd3c0", add_bg="#12352a", remove_bg="#3a1c18", gutter="#8b94ad",
    ),
)}
DEFAULT_PALETTE = "ember"

_active = PALETTES[DEFAULT_PALETTE]


def use(key: str | None) -> bool:
    global _active
    if key in PALETTES:
        _active = PALETTES[key]
        return True
    return False


def active() -> Palette:
    return _active


class _Tokens:
    def __getattr__(self, name: str) -> str:
        return getattr(_active, name)


t = _Tokens()
