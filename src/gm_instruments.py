"""
General MIDI Instrument Definitions
Contains the complete list of 128 GM instruments organized by categories
"""
from typing import Dict, List, Tuple

# GM Instrument categories and their instruments
# Format: (program_number, instrument_name) - MIDI uses 0-based program numbers (0-127)
GM_INSTRUMENTS = {
    "Piano": [
        (0, "Acoustic Grand Piano"),
        (1, "Bright Acoustic Piano"),
        (2, "Electric Grand Piano"),
        (3, "Honky-tonk Piano"),
        (4, "Electric Piano 1"),
        (5, "Electric Piano 2"),
        (6, "Harpsichord"),
        (7, "Clavi"),
    ],
    "Chromatic Percussion": [
        (8, "Celesta"),
        (9, "Glockenspiel"),
        (10, "Music Box"),
        (11, "Vibraphone"),
        (12, "Marimba"),
        (13, "Xylophone"),
        (14, "Tubular Bells"),
        (15, "Dulcimer"),
    ],
    "Organ": [
        (16, "Drawbar Organ"),
        (17, "Percussive Organ"),
        (18, "Rock Organ"),
        (19, "Church Organ"),
        (20, "Reed Organ"),
        (21, "Accordion"),
        (22, "Harmonica"),
        (23, "Tango Accordion"),
    ],
    "Guitar": [
        (24, "Acoustic Guitar (nylon)"),
        (25, "Acoustic Guitar (steel)"),
        (26, "Electric Guitar (jazz)"),
        (27, "Electric Guitar (clean)"),
        (28, "Electric Guitar (muted)"),
        (29, "Overdriven Guitar"),
        (30, "Distortion Guitar"),
        (31, "Guitar harmonics"),
    ],
    "Bass": [
        (32, "Acoustic Bass"),
        (33, "Electric Bass (finger)"),
        (34, "Electric Bass (pick)"),
        (35, "Fretless Bass"),
        (36, "Slap Bass 1"),
        (37, "Slap Bass 2"),
        (38, "Synth Bass 1"),
        (39, "Synth Bass 2"),
    ],
    "Strings": [
        (40, "Violin"),
        (41, "Viola"),
        (42, "Cello"),
        (43, "Contrabass"),
        (44, "Tremolo Strings"),
        (45, "Pizzicato Strings"),
        (46, "Orchestral Harp"),
        (47, "Timpani"),
    ],
    "Ensemble": [
        (48, "String Ensemble 1"),
        (49, "String Ensemble 2"),
        (50, "SynthStrings 1"),
        (51, "SynthStrings 2"),
        (52, "Choir Aahs"),
        (53, "Voice Oohs"),
        (54, "Synth Voice"),
        (55, "Orchestra Hit"),
    ],
    "Brass": [
        (56, "Trumpet"),
        (57, "Trombone"),
        (58, "Tuba"),
        (59, "Muted Trumpet"),
        (60, "French Horn"),
        (61, "Brass Section"),
        (62, "SynthBrass 1"),
        (63, "SynthBrass 2"),
    ],
    "Reed": [
        (64, "Soprano Sax"),
        (65, "Alto Sax"),
        (66, "Tenor Sax"),
        (67, "Baritone Sax"),
        (68, "Oboe"),
        (69, "English Horn"),
        (70, "Bassoon"),
        (71, "Clarinet"),
    ],
    "Pipe": [
        (72, "Piccolo"),
        (73, "Flute"),
        (74, "Recorder"),
        (75, "Pan Flute"),
        (76, "Blown Bottle"),
        (77, "Shakuhachi"),
        (78, "Whistle"),
        (79, "Ocarina"),
    ],
    "Synth Lead": [
        (80, "Lead 1 (square)"),
        (81, "Lead 2 (sawtooth)"),
        (82, "Lead 3 (calliope)"),
        (83, "Lead 4 (chiff)"),
        (84, "Lead 5 (charang)"),
        (85, "Lead 6 (voice)"),
        (86, "Lead 7 (fifths)"),
        (87, "Lead 8 (bass + lead)"),
    ],
    "Synth Pad": [
        (88, "Pad 1 (new age)"),
        (89, "Pad 2 (warm)"),
        (90, "Pad 3 (polysynth)"),
        (91, "Pad 4 (choir)"),
        (92, "Pad 5 (bowed)"),
        (93, "Pad 6 (metallic)"),
        (94, "Pad 7 (halo)"),
        (95, "Pad 8 (sweep)"),
    ],
    "Synth Effects": [
        (96, "FX 1 (rain)"),
        (97, "FX 2 (soundtrack)"),
        (98, "FX 3 (crystal)"),
        (99, "FX 4 (atmosphere)"),
        (100, "FX 5 (brightness)"),
        (101, "FX 6 (goblins)"),
        (102, "FX 7 (echoes)"),
        (103, "FX 8 (sci-fi)"),
    ],
    "Ethnic": [
        (104, "Sitar"),
        (105, "Banjo"),
        (106, "Shamisen"),
        (107, "Koto"),
        (108, "Kalimba"),
        (109, "Bag pipe"),
        (110, "Fiddle"),
        (111, "Shanai"),
    ],
    "Percussive": [
        (112, "Tinkle Bell"),
        (113, "Agogo"),
        (114, "Steel Drums"),
        (115, "Woodblock"),
        (116, "Taiko Drum"),
        (117, "Melodic Tom"),
        (118, "Synth Drum"),
        (119, "Reverse Cymbal"),
    ],
    "Sound Effects": [
        (120, "Guitar Fret Noise"),
        (121, "Breath Noise"),
        (122, "Seashore"),
        (123, "Bird Tweet"),
        (124, "Telephone Ring"),
        (125, "Helicopter"),
        (126, "Applause"),
        (127, "Gunshot"),
    ],
}

def get_all_gm_instruments() -> List[Tuple[int, str]]:
    """Get all GM instruments as a flat list of (program, name) tuples"""
    instruments = []
    for category_instruments in GM_INSTRUMENTS.values():
        instruments.extend(category_instruments)
    return sorted(instruments)

def get_gm_instrument_name(program: int) -> str:
    """Get GM instrument name by program number"""
    for category_instruments in GM_INSTRUMENTS.values():
        for prog, name in category_instruments:
            if prog == program:
                return name
    return f"Program {program}"

def get_gm_categories() -> List[str]:
    """Get list of GM instrument categories"""
    return list(GM_INSTRUMENTS.keys())

def get_instruments_in_category(category: str) -> List[Tuple[int, str]]:
    """Get instruments in a specific category"""
    return GM_INSTRUMENTS.get(category, [])