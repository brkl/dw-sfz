#!/usr/bin/python3
#
# Copyright 2016, roberto@zenvoid.org
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# createDWSFZ.py: build a simple SFZ instrument from a folder of samples
# autosampled by DirectWave, named like:
#
#     name_NOTE[_VELOCITY][_RR].wav
#
# Examples: test_D#2_127_4.wav, test_D#2_127.wav, test_D#2.wav
#
#   NOTE      note pitch (either "D#2" style or a plain MIDI number)
#   VELOCITY  max velocity of this layer (min = previous layer's max + 1)
#   RR        round-robin index for this note/velocity layer
#
# Both VELOCITY and RR are optional. When only one trailing number is
# present it is assumed to be VELOCITY unless --rr-only is given.

# Standalone, single-file script: no dependency on sfz.py or any
# third-party module, only the Python standard library.

import sys, logging
logging.basicConfig(level=logging.INFO, stream=sys.stderr, format='%(levelname)s: %(message)s')

import re, os, os.path, glob, time, argparse

NOTE_VALUE = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}


def convertNote(note):
	"""Convert a note name ("C4", "F#3", "60", ...) to a MIDI note number,
	or None if it can't be parsed. Mirrors SFZ.convertNote() from sfz.py."""
	if re.search(r'^[0-9]{1,3}$', note):
		noteNum = int(note)
		return noteNum if 0 <= noteNum <= 127 else None

	match = re.search(r'^([abcdefgABCDEFG])([b#]?)(-?[0-9])$', note)
	if not match:
		return None
	noteNum = NOTE_VALUE[match.group(1).upper()]
	if match.group(2) == '#':
		noteNum += 1
	elif match.group(2) == 'b':
		noteNum -= 1
	octave = int(match.group(3))
	if octave < -1 or octave > 9:
		return None
	noteNum += (octave + 1) * 12
	return noteNum if 0 <= noteNum <= 127 else None


def exportSFZ(soundBank, fileName=None):
	"""Minimal SFZ writer for the subset of opcodes this script produces."""
	outFile = open(fileName, 'w') if fileName else sys.stdout
	for hint in ('Name', 'Date', 'URL'):
		if hint in soundBank:
			outFile.write('//+ {}: {}\n'.format(hint, soundBank[hint]))

	for instrument in soundBank['instruments']:
		outFile.write('\n<global>\n')
		for key in sorted(instrument.keys()):
			if key == 'groups':
				continue
			if key[0].isupper():
				outFile.write(' //+ {}: {}\n'.format(key, instrument[key]))
			else:
				outFile.write(' {}={}\n'.format(key, instrument[key]))
		for group in instrument['groups']:
			outFile.write('\n<group>\n')
			for key in sorted(group.keys()):
				if key != 'regions':
					outFile.write(' {}={}\n'.format(key, group[key]))
			for region in group['regions']:
				outFile.write('<region>\n')
				hikey = region.get('hikey', 127)
				lokey = region.get('lokey', 0)
				pitch = region.get('pitch_keycenter', 60)
				if hikey == lokey and hikey == pitch:
					outFile.write(' key={}\n'.format(hikey))
				else:
					if lokey != 0:
						outFile.write(' lokey={}\n'.format(lokey))
					if hikey != 127:
						outFile.write(' hikey={}\n'.format(hikey))
					if 'pitch_keycenter' in region:
						outFile.write(' pitch_keycenter={}\n'.format(pitch))
				for key in sorted(region.keys()):
					if key in ('hikey', 'lokey', 'pitch_keycenter'):
						continue
					outFile.write(' {}={}\n'.format(key, region[key]))
	if fileName:
		outFile.close()


NOTE_ALPHA = r'[A-Ga-g][#b]?-?[0-9]{1,2}'
NOTE_NUM = r'[0-9]{1,3}'
FILE_RE = re.compile(
	r'^(?P<prefix>.+?)_(?P<note>' + NOTE_ALPHA + '|' + NOTE_NUM + r')'
	r'(?:_(?P<num1>[0-9]{1,3}))?(?:_(?P<num2>[0-9]{1,3}))?\.wav$',
	re.IGNORECASE)


def parseArgs():
	parser = argparse.ArgumentParser(
		description="Build a simple SFZ instrument from a folder of samples "
		"autosampled by DirectWave (name_NOTE[_VELOCITY][_RR].wav).")
	parser.add_argument('folder', help="Folder containing the .wav samples")
	parser.add_argument('-o', '--output',
		help="Output .sfz file (defaults to <folder>.sfz)")
	parser.add_argument('--name', help="Sound bank name (defaults to the folder name)")
	parser.add_argument('--instrument', help="Instrument name (defaults to the folder name)")
	parser.add_argument('--rr-only', action='store_true',
		help="Treat a single trailing number as a round-robin index instead of a velocity")
	parser.add_argument('--recursive', action='store_true',
		help="Also look for samples in subfolders")
	return parser.parse_args()


def findSamples(folder, recursive):
	if recursive:
		pattern = os.path.join(folder, '**', '*.wav')
	else:
		pattern = os.path.join(folder, '*.wav')
	return sorted(glob.glob(pattern, recursive=recursive), key=str.lower)


def parseFileName(fName, rrOnly):
	match = FILE_RE.search(os.path.basename(fName))
	if not match:
		logging.warning("Can't parse sample name, skipping: {}".format(fName))
		return None

	noteNum = convertNote(match.group('note'))
	if noteNum is None:
		logging.warning("Can't guess pitch from file name: {}".format(fName))
		return None

	num1 = match.group('num1')
	num2 = match.group('num2')
	velocity = None
	roundRobin = None
	if num1 is not None and num2 is not None:
		velocity = int(num1)
		roundRobin = int(num2)
	elif num1 is not None:
		if rrOnly:
			roundRobin = int(num1)
		else:
			velocity = int(num1)

	if velocity is not None and (velocity < 1 or velocity > 127):
		logging.warning("Velocity out of range (1-127) in {}, ignoring it".format(fName))
		velocity = None

	return {'file': fName, 'note': noteNum, 'velocity': velocity, 'rr': roundRobin}


def buildRegions(samples):
	# Group by note, then by velocity layer.
	byNote = {}
	for s in samples:
		byNote.setdefault(s['note'], {}).setdefault(s['velocity'], []).append(s)

	notes = sorted(byNote.keys())
	regions = []
	prevRegionsForKeyRange = None
	for i, noteNum in enumerate(notes):
		velLayers = byNote[noteNum]
		# Sort velocity layers ascending; None (no velocity info) is its own,
		# single, full-range layer.
		velKeys = sorted(v for v in velLayers.keys() if v is not None)
		hasNoVelInfo = None in velLayers

		# lokey is fixed by distributing the gap with the previous note;
		# hikey depends on the *next* note and is patched in a second pass
		# below (same gap-splitting approach as createSFZ.py).
		lokey = noteNum
		if i > 0:
			gap = noteNum - notes[i - 1] - 1
			leftGap = gap // 2
			lokey = noteNum - (gap - leftGap)
		regions_for_note = []

		prevHivel = 0
		layersToEmit = []
		if hasNoVelInfo and not velKeys:
			# Single layer covering the whole velocity range.
			layersToEmit.append((None, None, velLayers[None]))
		else:
			if hasNoVelInfo:
				logging.warning(
					"Note {}: mixing samples with and without velocity info; "
					"ignoring the ones without velocity".format(noteNum))
			for v in velKeys:
				layersToEmit.append((prevHivel + 1, v, velLayers[v]))
				prevHivel = v

		for lovel, hivel, files in layersToEmit:
			files = sorted(files, key=lambda s: (s['rr'] is None, s['rr'], s['file']))
			seqLength = len(files)
			for idx, s in enumerate(files):
				region = {
					'sample': s['file'].replace('\\', '/'),
					'pitch_keycenter': noteNum,
					'lokey': lokey,
					'hikey': noteNum,  # patched to real hikey below
				}
				if lovel is not None:
					region['lovel'] = lovel
				if hivel is not None:
					region['hivel'] = hivel
				if seqLength > 1:
					region['seq_length'] = seqLength
					region['seq_position'] = idx + 1
				regions_for_note.append(region)

		regions.append((noteNum, regions_for_note))

	# Second pass to fix up hikey using the actual neighbouring note gaps
	# (mirrors createSFZ.py's approach of adjusting the previous region once
	# the following note is known).
	for i, (noteNum, regionList) in enumerate(regions):
		hikey = noteNum
		if i < len(notes) - 1:
			gap = notes[i + 1] - noteNum - 1
			leftGap = gap // 2
			hikey = noteNum + leftGap
		for region in regionList:
			region['hikey'] = hikey

	flatRegions = []
	for _, regionList in regions:
		flatRegions.extend(regionList)
	return flatRegions


def main():
	args = parseArgs()

	folderName = os.path.basename(os.path.normpath(args.folder))
	if not args.name:
		args.name = folderName
	if not args.instrument:
		args.instrument = folderName
	if not args.output:
		args.output = folderName + '.sfz'

	files = findSamples(args.folder, args.recursive)
	if not files:
		logging.error("No .wav samples found in {}".format(args.folder))
		sys.exit(1)

	samples = []
	for fName in files:
		parsed = parseFileName(fName, args.rr_only)
		if parsed:
			samples.append(parsed)

	if not samples:
		logging.error("No samples could be parsed, aborting")
		sys.exit(1)

	regions = buildRegions(samples)

	soundBank = {
		'Name': args.name,
		'Date': time.strftime("%Y-%m-%d"),
		'instruments': [{
			'Instrument': args.instrument,
			'ampeg_release': '0.5',
			'groups': [{
				'loop_mode': 'no_loop',
				'regions': regions,
			}]
		}]
	}

	exportSFZ(soundBank, args.output)


if __name__ == '__main__':
	main()
