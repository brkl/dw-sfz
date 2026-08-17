# FreePats-Tools

Tools to manage, create and convert sound fonts, collections of sampled
musical instruments and sound banks. Originally created for the FreePats
project: http://freepats.zenvoid.org/


## Dependencies

Requires Python 3 with dateutil, soundfile and numpy modules. This will
install the required dependencencies on Debian and derived distributions:

    apt-get install python3 python3-dateutil python3-soundfile python3-numpy


## Usage

There are four programs included:

* createSFZ.py: Takes audio files as input and writes to stdout a SFZ template
for them.

* createDWSFZ.py: Takes a folder of samples autosampled by DirectWave and
writes a SFZ instrument, automatically splitting velocity layers and
round-robins. See "createDWSFZ.py" below.

* mergeSFZ.py: Combines several SFZ files into a single one. See "mergeSFZ.py"
below.

* convertSoundBank.py: Process a sound bank and writes another file, possibly
converted to a different format.


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

If the output file already exists, the new instrument is appended to it
instead of replacing it, which lets you build up a multi-instrument bank one
folder at a time:

    createDWSFZ.py samples/Piano -o Bank.sfz --name "My Bank"
    createDWSFZ.py samples/Drums -o Bank.sfz

The instrument name is always derived from the folder (or `--instrument`).
The bank name is resolved as: an explicit `--name`, if given; otherwise the
existing bank's name when appending; otherwise the folder name. In other
words, appending an instrument never changes the bank's name unless you pass
`--name` explicitly.

Run `createDWSFZ.py -h` for the full list of options.

Each run prints a short summary to stderr, e.g.:

    INFO: Wrote MyPatch.sfz (42 regions)
    INFO:   40 samples used, 2 skipped
    INFO:   12 notes mapped
    INFO:   18 velocity layers total (1.5 per note on average)
    INFO:   3 round-robin groups, up to 4 samples each

As with createSFZ.py, the generated SFZ file may need manual editing (e.g. to
shorten the instrument name for SF2 compatibility, or to add loop points).


### mergeSFZ.py

mergeSFZ.py combines any number of SFZ files into a single one:

    mergeSFZ.py Piano.sfz Drums.sfz -o Combined.sfz

Instrument names are always prefixed with their source file's name (e.g.
`Piano_Grand Piano`) so instruments never collide between files; if a
collision still happens, a number is appended.

Bank names ("//+ Name:" hints) are handled like this:

* If `--name` is given, every instrument from every input file is put into a
  single bank with that name, discarding each file's own bank name:

      mergeSFZ.py Piano.sfz Drums.sfz -o Combined.sfz --name "My Bank"

* Otherwise, each input file keeps its own bank name. Files that share the
  same bank name are combined under that one bank; files with different bank
  names each keep their own bank inside the merged file (the SFZ format has
  only one bank name per file, so in this case each bank's first instrument
  carries a `//+ Name:` annotation instead of a single top-of-file one).

Sample paths are automatically rewritten to stay correct relative to the
output file's location, even if the input files live in different folders.

Run `mergeSFZ.py -h` for the full list of options.


convertSoundBank.py can be used to validate and convert the SFZ file. When
converted to SF2, global options included within `<global>` will be converted
to global instrument options that can be overriden in subsequent groups or
regions.

This example will create a SF2 sound font.

    convertSoundBank.py grandPiano.sfz grandPiano.sf2

The resulting file grandPiano.sf2 should be ready to be used with fluidsynth,
qsynth, or any other program that handle SF2 files. It can also be open with a
sound font editor (swami, polyphone...) and inspect or continue editing its
contents.


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
