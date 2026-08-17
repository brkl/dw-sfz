# FreePats-Tools

Tools to manage, create and convert sound fonts, collections of sampled
musical instruments and sound banks. Originally created for the FreePats
project: http://freepats.zenvoid.org/


## Dependencies

Requires Python 3 with dateutil, soundfile and numpy modules. This will
install the required dependencencies on Debian and derived distributions:

    apt-get install python3 python3-dateutil python3-soundfile python3-numpy


## Usage

There are three programs included:

* createSFZ.py: Takes audio files as input and writes to stdout a SFZ template
for them.

* createDWSFZ.py: Takes a folder of samples autosampled by DirectWave and
writes a single, standard SFZ instrument, automatically splitting velocity
layers and round-robins. See "createDWSFZ.py" below.

* convertSoundBank.py: Process one or more sound banks and write a single
output file, possibly converted to a different format. This is also how you
combine several SFZ files (however they were made) into one SF2 soundfont,
each as its own preset. See "convertSoundBank.py" below. On Windows,
`CombineToSF2.bat` gives you a drag-and-drop front end for this.


createSFZ.py is useful to create a new sound bank in SFZ format. It accepts a
collection of samples as a list of arguments and writes a template to the
standard output.

The SFZ format is composed of text that can be modified with any text editor
to complete the missing parts. Later, it can be converted to other formats
with the convertSoundBank.py program.

createSFZ.py will try to guess the pitch of each sample from its file name.
For this reason, each sample must be named with a suffix indicating its note.
It accepts either standard MIDI numbers (where 60 is middle C), or English
alphabetic notation plus an octave number (where C4 is middle C).

Examples:

    createSFZ.py piano_C4.wav piano_C5.wav piano_F#4.wav piano_F#5.wav
    createSFZ.py samples/*.wav > soundBank.sfz


Generated output will look like this:

    //+ Name: Unnamed sound bank
    //+ Date: 2016-12-19

    <global>
     //+ Instrument: Unnamed instrument
     ampeg_release=0.5

    <group>
     loop_mode=no_loop
    <region>
     hikey=62
     pitch_keycenter=60
     sample=piano_C4.wav
    <region>
     lokey=63
     hikey=68
     pitch_keycenter=66
     sample=piano_F#4.wav
    <region>
     lokey=69
     hikey=74
     pitch_keycenter=72
     sample=piano_C5.wav
    <region>
     lokey=75
     pitch_keycenter=78
     sample=piano_F#5.wav


Lines starting with // are comments. Lines starting with //+ contain hints
that will be processed by these tools to provide additional information and
aid conversion between different formats. They will be ignored by SFZ players.

There are a few things that should be edited. In particular:

* Name of the sound bank and instrument. For compatibility with the SF2 format,
the instrument name should be no longer than 19 characters.

* If samples contain loops, `loop_mode` instruction should be modified and each
sample should have `loop_start` and `loop_end` information added.


### createDWSFZ.py

createDWSFZ.py is a standalone script (it has no dependency on the other files
in this repository, so it can be copied and used on its own) that builds a
SFZ instrument from a folder of samples autosampled by DirectWave.

Samples must be named:

    name_NOTE[_VELOCITY][_RR].wav

* `NOTE` is the note pitch, either English alphabetic notation plus an octave
  number (e.g. `D#2`) or a plain MIDI number.
* `VELOCITY` (optional) is the max velocity of that layer's samples. The
  layer's minimum velocity is one more than the previous (lower) layer's max.
* `RR` (optional) is the round-robin index for that note/velocity layer.

`VELOCITY` and `RR` don't have to be present on every file. If only one
trailing number is present it is assumed to be `VELOCITY`; pass `--rr-only`
if it should be interpreted as the round-robin index instead.

By default the sound bank name, instrument name and output file all default
to the folder name, so the simplest usage is:

    createDWSFZ.py MyPatch

which reads every `.wav` file in `MyPatch/` and writes `MyPatch.sfz`. Other
options:

    createDWSFZ.py samples/Piano -o Piano.sfz --name "Grand Piano"
    createDWSFZ.py samples/Drums --rr-only --recursive

Each run always writes a single, standard, spec-compliant SFZ instrument (no
proprietary multi-instrument tricks) -- to combine several of these, or any
other ready-made `.sfz` files, into one soundfont, see convertSoundBank.py
below.

Run `createDWSFZ.py -h` for the full list of options.

Each run prints a short summary to stderr, e.g.:

    INFO: Wrote MyPatch.sfz (42 regions)
    INFO:   40 samples used, 2 skipped
    INFO:   12 notes mapped
    INFO:   18 velocity layers total (1.5 per note on average)
    INFO:   3 round-robin groups, up to 4 samples each

As with createSFZ.py, the generated SFZ file may need manual editing (e.g. to
shorten the instrument name for SF2 compatibility, or to add loop points).


### convertSoundBank.py

convertSoundBank.py can be used to validate and convert a SFZ file. When
converted to SF2, global options included within `<global>` will be converted
to global instrument options that can be overriden in subsequent groups or
regions.

This example will create a SF2 sound font from a single SFZ file:

    convertSoundBank.py grandPiano.sfz grandPiano.sf2

The resulting file grandPiano.sf2 should be ready to be used with fluidsynth,
qsynth, or any other program that handles SF2 files. It can also be opened
with a sound font editor (swami, polyphone...) to inspect or continue editing
its contents.

You can also give it several `.sfz` files at once (however they were made --
by createDWSFZ.py or anything else) to combine them into a single `.sf2`
soundfont, with each input file becoming its own separate preset (never
layered or merged together):

    convertSoundBank.py Piano.sfz Drums.sfz Combined.sf2
    convertSoundBank.py Piano.sfz Drums.sfz Combined.sf2 --name "My Bank"

The last path is always the output file; combining is only supported when
that output is `.sf2` (there is no standard way to represent several
separate instruments inside one `.sfz` file, so this tool won't produce one).
Each preset's name comes from the source file's own instrument/bank name if
it has one, otherwise its file name, truncated and de-duplicated with a
numeric suffix as needed to fit SF2's 19-character limit. Sample files are
referenced from their original location and are never moved or copied, even
if the input files live in entirely different folders (or drives).

`convertSoundBank.py`'s SFZ reader is more permissive than a strict
implementation of the format: it accepts real-world `.sfz` files with
opcodes or values outside what this repository's own tools would ever
produce (e.g. files made by other software), preserving anything it doesn't
specifically need instead of rejecting the file.

Run `convertSoundBank.py -h` for the full list of options.

On Windows, `CombineToSF2.bat` gives you an interactive front end for the
combine feature, useful when the files you want to combine live in several
different folders: run it, type a bank name (and optionally an output path),
then drag and drop `.sfz` files onto the console window -- one at a time or
several at once -- pressing Enter after each drop. Press Enter with nothing
dropped when you're done, and it runs convertSoundBank.py for you.


## Limitations

* Has only been tested on Linux.

* Only SFZ to SF2 conversion is available. The opposite conversion from SF2 to
SFZ is not done yet. Other formats are missing.

* Supports a minimal subset of SFZ opcodes.

This software supports a small set of features, and is only useful to convert
very simple sound fonts, please note that on most cases the resulting file
will require manual editing.


## License

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
