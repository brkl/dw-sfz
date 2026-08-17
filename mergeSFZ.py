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

import sys, logging
logging.basicConfig(level=logging.INFO, stream=sys.stderr, format='%(levelname)s: %(message)s')

import os, os.path, time, argparse, textwrap, copy
from sfz import SFZ


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
	sfz = SFZ()
	if not sfz.importSFZ(fileName):
		logging.error("Could not read: {}".format(fileName))
		return None
	return sfz.soundBank


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

	sfz = SFZ()
	sfz.soundBank = mergedBank
	if not sfz.exportSFZ(args.output):
		sys.exit(1)

	totalInstruments = sum(len(v) for v in groups.values())
	logging.info("Wrote {} ({} file{} merged, {} instrument{}, {} bank{})".format(
		args.output, fileCount, '' if fileCount == 1 else 's',
		totalInstruments, '' if totalInstruments == 1 else 's',
		len(order), '' if len(order) == 1 else 's'))


if __name__ == '__main__':
	main()
