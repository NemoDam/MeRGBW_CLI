"""
scenes.py - Scene catalog for the TG201A device (MeRGBw).

Structure:
  Each scene is a Scene(name, scene_id, speed) object.
  scene_id : byte sent in CMD 0x06 (SET_SCENE)
  speed    : default value for CMD 0x0F (SET_SPEED), range 0-100

Source:
  capture btsnoop_hci_altre_scene.cfa (sequential scroll in the app,
  109 scenes in exact order, scene_id verified 1:1 against HCI traffic).
  speed=50 default: the capture consistently used speed=50 for this series.

Gap scene_id 76-83: missing from the capture, not exposed in the app,
  likely reserved or not implemented in the current firmware.

Note on original English (classic/festival) names:
  All matching IDs (e.g. 2=Symphony, 23=Chase, 59=Aurora, etc.)
  correspond to scenes already present in this list; the original
  names are documented in the inline comment of each entry.

Music scenes (microphone mode):
  MusicScene(name, scene_id) object.
  scene_id : byte sent in CMD 0x07 (SET_SCENE_MIC)
  Speed is not used (CMD 0x0F is not sent in this mode).
  Source: capture btsnoop_hci_20260610010612.cfa, 6 scenes in sequential
  order, scene_id 1-6 verified 1:1 against HCI traffic.
"""

from __future__ import annotations
from dataclasses import dataclass


# --- Dataclass ----------------------------------------------------------------

@dataclass(frozen=True)
class Scene:
    name:     str
    scene_id: int   # byte sent in CMD 0x06
    speed:    int   # default speed 0-100


@dataclass(frozen=True)
class MusicScene:
    name:     str
    scene_id: int   # byte sent in CMD 0x07 (SET_SCENE_MIC)


# --- Scene catalog (109) --------------------------------------------------------
# Order identical to the sequential scroll in the MeRGBw app.
# scene_id verified 1:1 from capture btsnoop_hci_altre_scene.cfa.
# Gap 76-83: not present in the capture (missing in firmware).

ALL_SCENES: list[Scene] = [

    # -- Cycle / multi-color -------------------------------------------------
    Scene("Cycle",                            1,   50),  # [classic alias: n/a]
    Scene("Fantastic color",                  2,   50),  # [classic: Symphony]
    Scene("Seven-color energy",               3,   50),  # [classic: Energy]
    Scene("Seven-color jump",                 4,   50),  # [classic: Jump]
    Scene("Red-green-blue jump",              5,   50),  # [festival: New Year]
    Scene("Yellow-cyan-violet jump",          6,   50),  # [festival: Party]
    Scene("Seven-color flash",                7,   50),  # [classic: Vitality]
    Scene("Red-green-blue flash",             8,   50),  # [festival: Christmas]
    Scene("Yellow-cyan-violet flash",         9,   50),
    Scene("Seven-color gradient",             10,  50),

    # -- Alternating gradient -------------------------------------------------
    Scene("Alternating red-yellow gradient",     11, 50),  # [festival: Halloween]
    Scene("Alternating red-violet gradient",     12, 50),  # [festival: Romantic]
    Scene("Alternating green-cyan gradient",     13, 50),  # [classic: Forest]
    Scene("Alternating green-yellow gradient",   14, 50),
    Scene("Alternating blue-violet gradient",    15, 50),

    # -- Accumulation -----------------------------------------------------------
    Scene("Red accumulation",     16, 50),  # [classic: Accumulation]
    Scene("Green accumulation",   17, 50),
    Scene("Blue accumulation",    18, 50),
    Scene("Yellow accumulation",  19, 50),
    Scene("Cyan accumulation",    20, 50),
    Scene("Violet accumulation",  21, 50),
    Scene("White accumulation",   22, 50),

    # -- Chase --------------------------------------------------------------------
    Scene("Seven-color chase",       23, 50),  # [classic: Chase]
    Scene("Red-green-blue chase",    24, 50),
    Scene("Yellow-cyan-violet chase", 25, 50),

    # -- Drift ----------------------------------------------------------------------
    Scene("Seven-color drift",       26, 50),  # [classic: Rainbow]
    Scene("Red-green-blue drift",    27, 50),
    Scene("Yellow-cyan-violet drift", 28, 50),

    # -- Spread -------------------------------------------------------------------
    Scene("Seven-color spread",   29, 50),  # [festival: Ball]
    Scene("Red-green-blue spread", 30, 50),
    Scene("Yellow-cyan spread",    31, 50),

    # -- Melody close -----------------------------------------------------------
    Scene("Seven-color melody close",       32, 50),  # [classic: Melody]
    Scene("Red-green-blue melody close",    33, 50),
    Scene("Yellow-cyan-violet melody close", 34, 50),

    # -- Opening and closing ---------------------------------------------------
    Scene("Seven-color opening and closing",       35, 50),  # [classic: Ephemeral]
    Scene("Red-green-blue opening and closing",    36, 50),
    Scene("Yellow-cyan-violet opening and closing", 37, 50),
    Scene("Red opening and closing",    38, 50),
    Scene("Green opening and closing",  39, 50),
    Scene("Blue opening and closing",   40, 50),
    Scene("Yellow opening and closing", 41, 50),
    Scene("Cyan opening and closing",   42, 50),
    Scene("Violet opening and closing", 43, 50),
    Scene("White opening and closing",  44, 50),

    # -- Light-to-dark transition ------------------------------------------------
    Scene("Seven-color light-to-dark transition",       45, 50),  # [classic: Space Time]
    Scene("Red-green-blue light-to-dark transition",    46, 50),
    Scene("Violet-cyan-yellow light-to-dark transition", 47, 50),

    # -- Dark transition ------------------------------------------------------------
    Scene("Six-color dark transition (red)",    48, 50),  # [classic: Neon Lights]
    Scene("Six-color dark transition (green)",  49, 50),
    Scene("Six-color dark transition (blue)",   50, 50),
    Scene("Six-color dark transition (cyan)",   51, 50),
    Scene("Six-color dark transition (yellow)", 52, 50),
    Scene("Six-color dark transition (violet)", 53, 50),
    Scene("Six-color dark transition (white)",  54, 50),

    # -- Flowing water -------------------------------------------------------------
    Scene("Seven-color flowing water",       55, 50),  # [classic: Flow]
    Scene("Red-green-blue flowing water",    56, 50),
    Scene("Cyan-yellow-violet flowing water", 57, 50),
    Scene("Red-green flowing water",          58, 50),
    Scene("Green-blue flowing water",         59, 50),  # [classic: Aurora]
    Scene("Yellow-blue flowing water",        60, 50),
    Scene("Yellow-cyan flowing water",        61, 50),
    Scene("Cyan-violet flowing water",        62, 50),
    Scene("Black-white flowing water",        63, 50),

    # -- Flow -------------------------------------------------------------------------
    Scene("White-red-white flow",      64, 50),
    Scene("White-green-white flow",    65, 50),
    Scene("White-blue-white flow",     66, 50),
    Scene("White-yellow-white flow",   67, 50),
    Scene("White-cyan-white flow",     68, 50),
    Scene("White-violet-white flow",   69, 50),
    Scene("Red-white-red flow",        70, 50),
    Scene("Green-white-green flow",    71, 50),  # [classic: Green Jade]
    Scene("Blue-white-blue flow",      72, 50),
    Scene("Yellow-white-yellow flow",  73, 50),
    Scene("Cyan-white-cyan flow",      74, 50),
    Scene("Violet-white-violet flow",  75, 50),

    # scene_id 76-83: firmware gap, not present in the capture

    # -- Run -------------------------------------------------------------------------
    Scene("Red run",                  84, 50),
    Scene("Green run",                85, 50),
    Scene("Blue run",                 86, 50),
    Scene("Yellow run",               87, 50),
    Scene("Cyan run",                 88, 50),
    Scene("Violet run",               89, 50),
    Scene("White run",                90, 50),
    Scene("Seven-color run",          91, 50),  # [classic: Running]
    Scene("Red-green-blue run",       92, 50),
    Scene("Violet-cyan-yellow run",            93, 50),
    Scene("Blue-violet-cyan-yellow run",       94, 50),
    Scene("Blue-green-cyan-yellow run",        95, 50),

    # -- Run with dot --------------------------------------------------------------
    Scene("Run with red dot on white background",     96,  50),
    Scene("Run with green dot on red background",     97,  50),
    Scene("Run with blue dot on green background",    98,  50),
    Scene("Run with yellow dot on blue background",   99,  50),
    Scene("Run with cyan dot on yellow background",   100, 50),
    Scene("Run with violet dot on cyan background",   101, 50),
    Scene("Run with white dot on violet background",  102, 50),  # [festival: Valentine]
    Scene("Run with white dot on red background",     103, 50),
    Scene("Run with RGBYCV dot on red background",    104, 50),
    Scene("Run with RGBYCV dot on green background",  105, 50),
    Scene("Run with RGBYCV dot on blue background",   106, 50),
    Scene("Run with RGBYCV dot on yellow background", 107, 50),
    Scene("Run with RGBYCV dot on cyan background",   108, 50),
    Scene("Run with RGBYCV dot on violet background", 109, 50),  # [classic: Pink Light]
    Scene("Run with RGBYCV dot on white background",  110, 50),
    Scene("Run with green dot on blue background",    111, 50),  # [festival: Ghost]
    Scene("Run with green dot on red background",     112, 50),
    Scene("Run with red dot on blue background",      113, 50),  # [classic: Alarm]
    Scene("Run with cyan dot on yellow background",   114, 50),
    Scene("Run with violet dot on yellow background", 115, 50),
    Scene("Run with white dot on yellow background",  116, 50),  # [festival: Candlelight]
    Scene("Run with yellow dot on white background",  117, 50),
]


# --- Search indexes (classic scenes) ----------------------------------------------

# By name (case-insensitive)
_BY_NAME: dict[str, Scene] = {s.name.lower(): s for s in ALL_SCENES}

# By scene_id (first occurrence wins, list is ordered by ID)
_BY_ID: dict[int, Scene] = {s.scene_id: s for s in ALL_SCENES}


def get_scene(name: str) -> Scene | None:
    """Return the scene by name (case-insensitive), or None."""
    return _BY_NAME.get(name.lower())


def get_scene_by_id(scene_id: int) -> Scene | None:
    """Return the scene by numeric ID, or None."""
    return _BY_ID.get(scene_id)


# --- Music scene catalog (6) -------------------------------------------------------
# Microphone mode: CMD 0x07 (SET_SCENE_MIC), no CMD 0x0F (speed).
# scene_id verified 1:1 from capture btsnoop_hci_20260610010612.cfa.

ALL_MUSIC_SCENES: list[MusicScene] = [
    MusicScene("Spectrum1", 1),
    MusicScene("Spectrum2", 2),
    MusicScene("Spectrum3", 3),
    MusicScene("Flowing",   4),
    MusicScene("Rolling",   5),
    MusicScene("Rhythm",    6),
]


# --- Search indexes (music scenes) ---------------------------------------------------

_MUSIC_BY_NAME: dict[str, MusicScene] = {s.name.lower(): s for s in ALL_MUSIC_SCENES}
_MUSIC_BY_ID:   dict[int, MusicScene] = {s.scene_id: s for s in ALL_MUSIC_SCENES}


def get_music_scene(name: str) -> MusicScene | None:
    """Return the music scene by name (case-insensitive), or None."""
    return _MUSIC_BY_NAME.get(name.lower())


def get_music_scene_by_id(scene_id: int) -> MusicScene | None:
    """Return the music scene by numeric ID, or None."""
    return _MUSIC_BY_ID.get(scene_id)
