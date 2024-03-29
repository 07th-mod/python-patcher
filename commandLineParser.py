from __future__ import unicode_literals

import re

try:
	from typing import Optional
except:
	pass

class AriaStatusUpdate:
	regexAriaCompletionStatus = re.compile(r"#[0-9a-zA-Z]+\s([^/]+/[^/]+)\((100|\d\d|\d)%\)")
	regexAriaETA = re.compile(r"ETA:([^\]]+)")
	regexAriaConnectionAndSpeed = re.compile(r'CN:([^D]+)DL:([^E]+)', re.IGNORECASE)
	regexAriaChecksumError = re.compile(r'Checksum error detected\.\s*file=(.*)', re.IGNORECASE)

	def __init__(self, amountCompletedString, percentCompleted, numConnections, speed, ETAString):
		self.amountCompletedString = amountCompletedString
		self.percentCompleted = percentCompleted
		self.ETAString = ETAString
		self.speed = speed
		self.numConnections = numConnections

#Note: Sometimes can get lines like "99% 35615" without the - [filename] part. This will be missed by this parser.
class SevenZipStatusUpdate:
	#Note: extracted file count is OPTIONAL - if few files, 7zip omits it. In that case, match[2] = None
	regexSevenZipPercentComplete = re.compile(r"(100|\d\d|\d)%")                # use with .search()
	regexSevenZipFileCountAndName = re.compile(r"^\s*\d+ - *.*\s*$")    # use with .match()
	regexSevenZipFileCountOnly = re.compile(r"^\s*\d+\s*$")             # use with .match()
	regexSevenZipExtractionStarted = re.compile(r"^\s*Extracting archive:\s*.*") # use with .match()

	def __init__(self, percentCompleted, numItemsCompleted, currentlyProcessingFileName):
		self.percentCompleted = percentCompleted
		self.numItemsCompleted = numItemsCompleted
		self.currentlyProcessingFilename = currentlyProcessingFileName

class SeventhModStatusUpdate:
	regexSeventhModStatus = re.compile(r"<<< \s*Status:\s*(100|\d\d|\d)%\s*(.+) >>>")

	def __init__(self, overallPercentage, currentTask):
		# type: (int, str) -> None
		self.overallPercentage = overallPercentage
		self.currentTask = currentTask

# parse a line like: [#7f0d78 27MiB/910MiB(3%) CN:8 DL:4.2MiB ETA:3m27s]
#                or: [#99893f 1.1MiB/910MiB(0%) CN:8 DL:1.1MiB ETA:12m50s]
def tryGetAriaStatusUpdate(ariaStatusUpdateString):
	# type: (str) -> Optional[AriaStatusUpdate]
	match = AriaStatusUpdate.regexAriaCompletionStatus.search(ariaStatusUpdateString)
	if not match or len(match.groups()) < 2:
		return None

	amountCompletedString = match.group(1)
	percentCompleted = int(match.group(2))

	ETAString = "N/A"

	match = AriaStatusUpdate.regexAriaETA.search(ariaStatusUpdateString)
	if match:
		ETAString = match.groups()[0]

	# Search for num connections and speed separately so they don't cause the ETA search to fail
	match = AriaStatusUpdate.regexAriaConnectionAndSpeed.search(ariaStatusUpdateString)
	if match:
		numConnections = match.groups()[0]
		speed = match.groups()[1]
	else:
		numConnections = "N/A"
		speed = "N/A"

	return AriaStatusUpdate(amountCompletedString, percentCompleted, numConnections, speed, ETAString)

def tryGetAriaChecksumError(ariaChecksumErrorString):
	# type: (str) -> Optional[str]
	"""
	Matches a message like:
	"Checksum error detected. file=Umineko Question (Ch. 1-4) Downloads/Umineko-Graphics-1080p-v2.7z"
	"""
	match = AriaStatusUpdate.regexAriaChecksumError.search(ariaChecksumErrorString)
	return match.groups()[0] if match is not None else None

#if none of the other types of lines match, and you see a percent number (eg 54%), assume it's 7zip
def tryGetSevenZipPercent(sevenZipStatusUpdateString):
	# type: (str) -> Optional[str]
	match = SevenZipStatusUpdate.regexSevenZipPercentComplete.search(sevenZipStatusUpdateString)
	if not match or len(match.groups()) < 1:
		return None


	return int(match.groups()[0])

#look for 10211 - HigurashiEp02_Data\StreamingAs . ctrum\ps3\s02\02\130200358.txt
#or: 99% 10339 - HigurashiEp02_Data\StreamingAs . ctrum\ps3\s02\02\130200486.txt
def tryGetSevenZipFilecountAndFileNameString(sevenZipStatusUpdateString):
	# type: (str) -> Optional[str]
	#NOTE: 'match' is used here, not 'search'
	if SevenZipStatusUpdate.regexSevenZipFileCountAndName.match(sevenZipStatusUpdateString):
		return sevenZipStatusUpdateString

	return None

def tryGetSevenZipFileCount(sevenZipStatusUpdateString):
	# type: (str) -> Optional[str]
	# NOTE: 'match' is used here, not 'search'
	if SevenZipStatusUpdate.regexSevenZipFileCountOnly.match(sevenZipStatusUpdateString):
		return sevenZipStatusUpdateString

	return None

def tryGetSevenZipExtractionStarted(sevenZipStatusUpdateString):
	# type: (str) -> Optional[str]
	# NOTE: 'match' is used here, not 'search'
	if SevenZipStatusUpdate.regexSevenZipExtractionStarted.match(sevenZipStatusUpdateString):
		return sevenZipStatusUpdateString

	return None

def tryGetSevenZipTestArchive(sevenZipStatusUpdateString):
	# type: (str) -> Optional[str]
	if sevenZipStatusUpdateString.lstrip().startswith('Testing archive:'):
		return sevenZipStatusUpdateString

	return None

def tryGetOverallStatus(overallStatusString):
	match = SeventhModStatusUpdate.regexSeventhModStatus.search(overallStatusString)
	if not match or len(match.groups()) < 2:
		return None

	return SeventhModStatusUpdate(overallPercentage=int(match.group(1)), currentTask=match.group(2))

# Print a status update which will be recognized by the command line parser
def printSeventhModStatusUpdate(overallPercentage, currentTask):
	# type: (int, str) -> None
	print("<<< Status: {}% {} >>>".format(overallPercentage, currentTask))
