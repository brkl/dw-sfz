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

import sys, logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

import re, os, os.path, copy, argparse, textwrap
from sfz import SFZ
from sf2 import SF2

inputFormats = ['sfz']
outputFormats = ['sfz', 'sf2']

NOTE_VALUE = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}


def convertNote(note):
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


class PermissiveSFZReader:
	"""Reads any .sfz file, including ones with opcodes or values sfz.py's
	strict, whitelist-based parser would reject (e.g. real-world files not
	produced by this repository's own tools). Unlike sfz.py, it preserves
	any opcode or hint it doesn't specifically know about instead of
	dropping it or raising an error over out-of-range values."""

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

	# Opcodes the SF2 exporter (sf2.py) reads as a real int/float without
	# converting them itself; everything else is fine to leave as a plain
	# string, since sf2.py already calls int()/float() on those as needed.
	FLOAT_OPCODES = ('delay', 'ampeg_attack', 'ampeg_decay', 'ampeg_hold', 'ampeg_release')
	INT_OPCODES = ('lovel', 'hivel', 'loop_start', 'loop_end', 'seq_length', 'seq_position')

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
		elif lower in self.FLOAT_OPCODES:
			try:
				value = float(value)
			except ValueError:
				raise SFZParseError("Invalid number for '{}': {}".format(opcode, value))
		elif lower in self.INT_OPCODES:
			try:
				value = int(round(float(value)))
			except ValueError:
				raise SFZParseError("Invalid number for '{}': {}".format(opcode, value))
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


def loadSoundBank(fileName):
	"""Read an .sfz file with the permissive reader above (works on
	arbitrary, real-world .sfz files, not just ones written by this
	repository's own tools)."""
	reader = PermissiveSFZReader()
	if not reader.parseFile(fileName):
		return None
	return reader.soundBank


def guessFormat(fileName, knownFormats, kind):
	match = re.search(r'\.([a-z0-9]+)$', fileName.lower())
	if not match:
		logging.error("Can not guess format from file name: {}".format(fileName))
		return None
	fmt = match.group(1)
	if fmt not in knownFormats:
		logging.error("Unknown or unsupported {} format: {}".format(kind, fmt))
		return None
	return fmt


def parseArgs():
	parser = argparse.ArgumentParser(
		formatter_class=argparse.RawDescriptionHelpFormatter,
		description=textwrap.dedent("""\
			Process one or more INPUT sound banks and write a single OUTPUT
			file, possibly converted to a different format. Formats are
			guessed from file names. Supported formats in this version:

			    Input:  {inputFormats}
			    Output: {outputFormats}

			This program supports a limited subset of the SFZ format,
			extended with annotations which enable better control of the
			generated output files.

			If several INPUT files are given, OUTPUT must be a .sf2 file:
			each input file's instrument(s) become their own separate
			preset in the resulting soundfont (nothing is merged or
			layered together), and sample files are referenced from their
			original location -- nothing is moved or copied.""").format(
			inputFormats=", ".join(inputFormats).upper(),
			outputFormats=", ".join(outputFormats).upper()),
		epilog=textwrap.dedent("""\
			examples:
			  convertSoundBank.py grandPiano.sfz grandPiano.sf2
			  convertSoundBank.py Piano.sfz Drums.sfz Combined.sf2
			  convertSoundBank.py Piano.sfz Drums.sfz Combined.sf2 --name "My Bank\""""))
	parser.add_argument('paths', nargs='+', metavar='PATH',
		help="One or more INPUT files followed by the OUTPUT file")
	parser.add_argument('--name',
		help="Override the resulting bank's name "
		"(defaults to the single input's own name, or to 'Sound Bank' when combining)")
	args = parser.parse_args()
	if len(args.paths) < 2:
		parser.error("at least one INPUT and an OUTPUT are required")
	args.inputs = args.paths[:-1]
	args.output = args.paths[-1]
	return args


def uniqueName(name, used):
	"""Deduplicate name against used, keeping it within SF2's 19-char
	preset/instrument name limit."""
	name = name.encode('ascii', 'replace').decode('ascii')[:19]
	if name not in used:
		used.add(name)
		return name
	for n in range(2, 1000):
		suffix = str(n)
		candidate = (name[:19 - len(suffix)] + suffix)
		if candidate not in used:
			used.add(candidate)
			return candidate
	raise RuntimeError("Too many colliding instrument names")


def rebaseSample(sampleValue, sourceDir, outputDir):
	sampleValue = sampleValue.replace('\\', '/')
	if os.path.isabs(sampleValue):
		return sampleValue
	absPath = os.path.normpath(os.path.join(sourceDir, sampleValue))
	try:
		return os.path.relpath(absPath, outputDir).replace('\\', '/')
	except ValueError:
		# On Windows, relpath() fails if sourceDir and outputDir are on
		# different drives; fall back to an absolute path in that case.
		return absPath.replace('\\', '/')


def rebaseSamplePaths(instrument, sourceDir, outputDir):
	for group in instrument.get('groups', []):
		if 'sample' in group:
			group['sample'] = rebaseSample(group['sample'], sourceDir, outputDir)
		for region in group.get('regions', []):
			if 'sample' in region:
				region['sample'] = rebaseSample(region['sample'], sourceDir, outputDir)


def loadInstrumentsToCombine(fileName, outputDir, usedNames):
	"""Load one .sfz file's instrument(s) as separate presets: sample paths
	rebased relative to outputDir, names deduplicated and truncated to fit
	SF2's 19-character limit."""
	bank = loadSoundBank(fileName)
	if bank is None:
		return None

	sourceDir = os.path.dirname(os.path.abspath(fileName))
	stem = os.path.splitext(os.path.basename(fileName))[0]
	fallbackName = bank.get('Instrument') or bank.get('Name') or stem

	instruments = []
	for idx, instrument in enumerate(bank.get('instruments', [])):
		instrument = copy.deepcopy(instrument)
		rebaseSamplePaths(instrument, sourceDir, outputDir)
		baseName = instrument.get('Instrument') \
			or (fallbackName if idx == 0 else "{}_{}".format(fallbackName, idx + 1))
		instrument['Instrument'] = uniqueName(baseName, usedNames)
		instruments.append(instrument)
	return instruments


def combineToSF2(inputFiles, outputFile, name):
	outputDir = os.path.dirname(os.path.abspath(outputFile))
	usedNames = set()
	instruments = []
	for fileName in inputFiles:
		loaded = loadInstrumentsToCombine(fileName, outputDir, usedNames)
		if loaded is None:
			return False
		if not loaded:
			logging.warning("No instruments found in: {}".format(fileName))
		instruments.extend(loaded)

	if not instruments:
		logging.error("No instruments could be loaded, aborting")
		return False

	soundBank = {
		'Name': name or 'Sound Bank',
		'Path': outputDir,
		'instruments': instruments,
	}
	sf2 = SF2()
	if not sf2.exportSF2(soundBank, outputFile):
		return False

	logging.info("Wrote {} ({} file{} combined, {} preset{})".format(
		outputFile, len(inputFiles), '' if len(inputFiles) == 1 else 's',
		len(instruments), '' if len(instruments) == 1 else 's'))
	return True


def convertSingle(inputFile, outputFile, name):
	inputFormat = guessFormat(inputFile, inputFormats, 'input')
	outputFormat = guessFormat(outputFile, outputFormats, 'output')
	if not inputFormat or not outputFormat:
		return False

	logging.info("Reading and processing input file...")
	soundBank = loadSoundBank(inputFile)
	if soundBank is None:
		return False
	if name:
		soundBank['Name'] = name

	logging.info("Writing output file...")
	if outputFormat == 'sfz':
		sfz = SFZ()
		sfz.soundBank = soundBank
		if not sfz.exportSFZ(outputFile):
			return False
	elif outputFormat == 'sf2':
		sf2 = SF2()
		if not sf2.exportSF2(soundBank, outputFile):
			return False

	logging.info("Done: {}".format(outputFile))
	return True


def main():
	args = parseArgs()

	if len(args.inputs) == 1:
		ok = convertSingle(args.inputs[0], args.output, args.name)
	else:
		outputFormat = guessFormat(args.output, outputFormats, 'output')
		if outputFormat is None:
			sys.exit(1)
		if outputFormat != 'sf2':
			logging.error(
				"Combining multiple input files is only supported when "
				"the output is a .sf2 file")
			sys.exit(1)
		for inputFile in args.inputs:
			if guessFormat(inputFile, inputFormats, 'input') is None:
				sys.exit(1)
		ok = combineToSF2(args.inputs, args.output, args.name)

	if not ok:
		sys.exit(1)


if __name__ == '__main__':
	main()
