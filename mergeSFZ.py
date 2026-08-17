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
# mergeSFZ.py: combine several SFZ files into a single one.
#
# * If --name is given, every instrument from every input file is put into
#   a single bank with that name.
# * Otherwise, input files keep their own "//+ Name:" bank name. Files that
#   share the same bank name end up combined under that one bank; files
#   with different bank names each keep their own bank inside the merged
#   file (annotated with a "//+ Name:" hint on their first instrument).
#
# Instrument names are always prefixed with their source file's name (e.g.
# "pianoA_Grand Piano") so instruments never collide between files; if a
# collision still happens (e.g. two instruments from the same file with the
# same name), a number is appended.
#
# Standalone, single-file script: no dependency on sfz.py or any
# third-party module, only the Python standard library. Note that the
# built-in SFZ reader below is deliberately permissive: unlike sfz.py, it
# passes through any opcode or hint it doesn't specifically know about
# instead of dropping it, so merging is not limited to files this
# repository's own tools produced.

import sys, logging
logging.basicConfig(level=logging.INFO, stream=sys.stderr, format='%(levelname)s: %(message)s')

import re, os, os.path, time, argparse, textwrap, copy

NOTE_VALUE = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}


def convertNote(note):
	"""Convert a note name ("C4", "F#3", "60", ...) to a MIDI note number,
	or None if it can't be parsed."""
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


class SFZParseError(Exception):
	pass


HINT_RE = re.compile(r'//\+ ([a-zA-Z0-9_&.+-]+): +(\S.*)$')
NEXT_OPCODE_RE = re.compile(r'\s[a-zA-Z0-9_]+=')


class SFZReader:
	"""Minimal, permissive SFZ parser: preserves any opcode or hint found,
	without validating or restricting them to a known set."""

	def __init__(self):
		self.soundBank = {'instruments': []}
		self.instrument = {'groups': []}
		self.group = {'regions': []}
		self.region = {}
		self.insideInstrument = False
		self.insideGroup = False
		self.insideRegion = False

	def parseFile(self, fileName):
		path = os.path.dirname(fileName)
		if path:
			self.soundBank['Path'] = path
		try:
			inFile = open(fileName, 'r')
		except OSError:
			logging.error("Can not open file: {}".format(fileName))
			return False
		lineNumber = 0
		for line in inFile:
			lineNumber += 1
			try:
				self.processLine(line)
			except SFZParseError as e:
				logging.error("Error on line {} of file {}: {}".format(lineNumber, fileName, e))
				inFile.close()
				return False
		inFile.close()
		self.commitRegion()
		self.commitGroup()
		self.commitInstrument()
		return True

	def processLine(self, line):
		match = HINT_RE.search(line)
		if match:
			self.addOpcode(match.group(1), match.group(2).rstrip())
			return

		line = line.partition('//')[0].rstrip()
		while True:
			line = line.lstrip()
			if len(line) == 0:
				return

			if line[0] == '<':
				end = line.find('>')
				if end == -1:
					raise SFZParseError("Malformed header (missing '>')")
				header = line[1:end]
				if len(header) < 1:
					raise SFZParseError("Empty header")
				self.processHeader(header)
				line = line[end + 1:]
				continue

			end = line.find('=')
			if end == -1:
				raise SFZParseError("Malformed line (missing '=')")
			opcode = line[:end]
			if len(opcode) < 1:
				raise SFZParseError("Empty opcode name")
			line = line[end + 1:]
			if len(line) == 0:
				raise SFZParseError("Missing opcode value")

			match = re.search('[=<]', line)
			if not match:
				self.processOpcode(opcode, line.rstrip())
				return

			if line[match.start()] == '=':
				nextOpcode = NEXT_OPCODE_RE.search(line)
				if not nextOpcode:
					raise SFZParseError("Malformed line")
				value = line[:nextOpcode.start()].rstrip()
				line = line[nextOpcode.start():]
			else:
				value = line[:match.start()].rstrip()
				line = line[match.start():]

			self.processOpcode(opcode, value)

	def processHeader(self, header):
		if header == 'global':
			self.commitRegion()
			self.commitGroup()
			self.commitInstrument()
			self.insideInstrument = True
			self.insideGroup = False
			self.insideRegion = False
		elif header == 'group':
			self.commitRegion()
			self.commitGroup()
			self.insideInstrument = True
			self.insideGroup = True
			self.insideRegion = False
		elif header == 'region':
			self.commitRegion()
			self.insideInstrument = True
			self.insideRegion = True
		else:
			raise SFZParseError("Unknown header: <{}>".format(header))

	def processOpcode(self, opcode, value):
		lower = opcode.lower()
		if lower == 'sample':
			value = value.replace('\\', '/')
		elif lower == 'key':
			noteNum = convertNote(value)
			if noteNum is None:
				raise SFZParseError("Invalid note for 'key': {}".format(value))
			self.addOpcode('lokey', noteNum)
			self.addOpcode('hikey', noteNum)
			self.addOpcode('pitch_keycenter', noteNum)
			return
		elif lower in ('lokey', 'hikey', 'pitch_keycenter'):
			noteNum = convertNote(value)
			if noteNum is None:
				raise SFZParseError("Invalid note for '{}': {}".format(opcode, value))
			value = noteNum
		self.addOpcode(opcode, value)

	def addOpcode(self, opcode, value):
		if self.insideRegion:
			self.region[opcode] = value
		elif self.insideGroup:
			self.group[opcode] = value
		elif self.insideInstrument:
			self.instrument[opcode] = value
		else:
			self.soundBank[opcode] = value

	def commitRegion(self):
		if len(self.region) > 0:
			self.group['regions'].append(self.region)
		self.region = {}

	def commitGroup(self):
		if len(self.group['regions']) > 0:
			self.instrument['groups'].append(self.group)
		self.group = {'regions': []}

	def commitInstrument(self):
		if len(self.instrument['groups']) > 0:
			self.soundBank['instruments'].append(self.instrument)
		self.instrument = {'groups': []}


def renderHeader(soundBank):
	lines = []
	for hint in ('Name', 'Date', 'URL'):
		if hint in soundBank:
			lines.append('//+ {}: {}\n'.format(hint, soundBank[hint]))
	return ''.join(lines)


def renderInstrument(instrument):
	lines = []
	lines.append('\n<global>\n')
	for key in sorted(instrument.keys()):
		if key == 'groups':
			continue
		if key[0].isupper():
			lines.append(' //+ {}: {}\n'.format(key, instrument[key]))
		else:
			lines.append(' {}={}\n'.format(key, instrument[key]))
	for group in instrument['groups']:
		lines.append('\n<group>\n')
		for key in sorted(group.keys()):
			if key != 'regions':
				lines.append(' {}={}\n'.format(key, group[key]))
		for region in group['regions']:
			lines.append('<region>\n')
			hikey = region.get('hikey', 127)
			lokey = region.get('lokey', 0)
			pitch = region.get('pitch_keycenter', 60)
			if hikey == lokey and hikey == pitch:
				lines.append(' key={}\n'.format(hikey))
			else:
				if lokey != 0:
					lines.append(' lokey={}\n'.format(lokey))
				if hikey != 127:
					lines.append(' hikey={}\n'.format(hikey))
				if 'pitch_keycenter' in region:
					lines.append(' pitch_keycenter={}\n'.format(pitch))
			for key in sorted(region.keys()):
				if key in ('hikey', 'lokey', 'pitch_keycenter'):
					continue
				lines.append(' {}={}\n'.format(key, region[key]))
	return ''.join(lines)


def exportSFZ(soundBank, fileName=None):
	outFile = open(fileName, 'w') if fileName else sys.stdout
	outFile.write(renderHeader(soundBank))
	for instrument in soundBank['instruments']:
		outFile.write(renderInstrument(instrument))
	if fileName:
		outFile.close()


def parseArgs():
	parser = argparse.ArgumentParser(
		formatter_class=argparse.RawDescriptionHelpFormatter,
		description=textwrap.dedent("""\
			Combine several SFZ files into a single one.

			If --name is given, every instrument from every input file is
			put into a single bank with that name. Otherwise, each input
			file keeps its own bank name ("//+ Name:" hint): files that
			share the same bank name are combined under that one bank,
			files with different bank names each keep their own bank
			inside the merged file.

			Instrument names are always prefixed with their source file's
			name so they never collide between files."""),
		epilog=textwrap.dedent("""\
			examples:
			  mergeSFZ.py Piano.sfz Drums.sfz -o Combined.sfz
			  mergeSFZ.py Piano.sfz Drums.sfz -o Combined.sfz --name "My Bank"
			  mergeSFZ.py samples/*.sfz -o Everything.sfz"""))
	parser.add_argument('files', nargs='+', help="Input .sfz files to merge")
	parser.add_argument('-o', '--output', required=True, help="Output .sfz file")
	parser.add_argument('--name',
		help="Put every instrument in a single bank with this name "
		"(defaults to keeping each input file's own bank name)")
	return parser.parse_args()


def loadBank(fileName):
	reader = SFZReader()
	if not reader.parseFile(fileName):
		return None
	return reader.soundBank


def uniqueName(name, used):
	if name not in used:
		used.add(name)
		return name
	n = 2
	while "{}_{}".format(name, n) in used:
		n += 1
	finalName = "{}_{}".format(name, n)
	used.add(finalName)
	return finalName


def rebaseSample(sampleValue, sourceDir, outputDir):
	sampleValue = sampleValue.replace('\\', '/')
	absPath = sampleValue if os.path.isabs(sampleValue) \
		else os.path.normpath(os.path.join(sourceDir, sampleValue))
	if os.path.isabs(sampleValue):
		return absPath.replace('\\', '/')
	return os.path.relpath(absPath, outputDir).replace('\\', '/')


def rebaseSamplePaths(instrument, sourceDir, outputDir):
	for group in instrument.get('groups', []):
		if 'sample' in group:
			group['sample'] = rebaseSample(group['sample'], sourceDir, outputDir)
		for region in group.get('regions', []):
			if 'sample' in region:
				region['sample'] = rebaseSample(region['sample'], sourceDir, outputDir)


def loadInstruments(fileName, outputDir, usedNames):
	"""Load one file's instruments, with sample paths rebased relative to
	outputDir and instrument names prefixed/deduplicated."""
	bank = loadBank(fileName)
	if bank is None:
		return None, None

	sourceDir = os.path.dirname(os.path.abspath(fileName))
	stem = os.path.splitext(os.path.basename(fileName))[0]
	bankName = bank.get('Name', stem)

	instruments = []
	for idx, instrument in enumerate(bank.get('instruments', [])):
		instrument = copy.deepcopy(instrument)
		rebaseSamplePaths(instrument, sourceDir, outputDir)
		baseName = instrument.get('Instrument', stem if idx == 0 else "{}_{}".format(stem, idx + 1))
		instrument['Instrument'] = uniqueName("{}_{}".format(stem, baseName), usedNames)
		instruments.append(instrument)

	return bankName, instruments


def main():
	args = parseArgs()
	outputDir = os.path.dirname(os.path.abspath(args.output))
	usedNames = set()

	groups = {}
	order = []
	fileCount = 0
	for fName in args.files:
		bankName, instruments = loadInstruments(fName, outputDir, usedNames)
		if instruments is None:
			sys.exit(1)
		fileCount += 1
		key = None if args.name else bankName
		if key not in groups:
			groups[key] = []
			order.append(key)
		groups[key].extend(instruments)

	if args.name:
		mergedBank = {
			'Name': args.name,
			'Date': time.strftime("%Y-%m-%d"),
			'instruments': groups[None],
		}
	elif len(order) == 1:
		mergedBank = {
			'Name': order[0],
			'Date': time.strftime("%Y-%m-%d"),
			'instruments': groups[order[0]],
		}
	else:
		allInstruments = []
		for bankName in order:
			group = groups[bankName]
			group[0] = dict(group[0])
			group[0]['Name'] = bankName
			allInstruments.extend(group)
		mergedBank = {
			'Date': time.strftime("%Y-%m-%d"),
			'instruments': allInstruments,
		}

	exportSFZ(mergedBank, args.output)

	totalInstruments = sum(len(v) for v in groups.values())
	logging.info("Wrote {} ({} file{} merged, {} instrument{}, {} bank{})".format(
		args.output, fileCount, '' if fileCount == 1 else 's',
		totalInstruments, '' if totalInstruments == 1 else 's',
		len(order), '' if len(order) == 1 else 's'))


if __name__ == '__main__':
	main()
