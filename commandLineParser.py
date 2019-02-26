import re

class AriaStatusUpdate:
	regexAriaCompletionStatus = re.compile(r"#[0-9a-zA-Z]+\s([^/]+/[^/]+)\((\d+)%\)")
	regexAriaETA = re.compile(r"ETA:([^\]]+)")

	def __init__(self, amountCompletedString, percentCompleted, ETAString):
		self.amountCompletedString = amountCompletedString
		self.percentCompleted = percentCompleted
		self.ETAString = ETAString

#Note: Sometimes can get lines like "99% 35615" without the - [filename] part. This will be missed by this parser.
class SevenZipStatusUpdate:
	#Note: extracted file count is OPTIONAL - if few files, 7zip omits it. In that case, match[2] = None
	regexSevenZipPercentComplete = re.compile(r"(\d+)%")
	regexSevenZipFileCountAndName = re.compile(r"\s*(\d+ - *.*)\s*")

	def __init__(self, percentCompleted, numItemsCompleted, currentlyProcessingFileName):
		self.percentCompleted = percentCompleted
		self.numItemsCompleted = numItemsCompleted
		self.currentlyProcessingFilename = currentlyProcessingFileName

class SeventhModStatusUpdate:
	regexSeventhModStatus = re.compile(r"<<< \s*Status:\s*(\d+)%\s*\[\[\s*([^>]+)\]\] >>>")

	def __init__(self, overallPercentage, currentTask):
		# type: (int, str) -> None
		self.overallPercentage = overallPercentage
		self.currentTask = currentTask

# parse a line like: [#7f0d78 27MiB/910MiB(3%) CN:8 DL:4.2MiB ETA:3m27s]
#                or: [#99893f 1.1MiB/910MiB(0%) CN:8 DL:1.1MiB ETA:12m50s]
def tryGetAriaStatusUpdate(ariaStatusUpdateString):
	# type: (str) -> AriaStatusUpdate
	match = AriaStatusUpdate.regexAriaCompletionStatus.search(ariaStatusUpdateString)
	if not match or len(match.groups()) < 2:
		return None

	amountCompletedString = match.group(1)
	percentCompleted = int(match.group(2))

	match = AriaStatusUpdate.regexAriaETA.search(ariaStatusUpdateString)
	if not match or len(match.groups()) < 1:
		return None

	ETAString = match.group(1)

	return AriaStatusUpdate(amountCompletedString, percentCompleted, ETAString)

#if none of the other types of lines match, and you see a percent number (eg 54%), assume it's 7zip
def tryGetSevenZipPercent(sevenZipStatusUpdateString):
	# type: (str) -> int
	match = SevenZipStatusUpdate.regexSevenZipPercentComplete.search(sevenZipStatusUpdateString)
	if not match or len(match.groups()) < 1:
		return None


	return int(match.groups()[0])

#look for 10211 - HigurashiEp02_Data\StreamingAs . ctrum\ps3\s02\02\130200358.txt
#or: 99% 10339 - HigurashiEp02_Data\StreamingAs . ctrum\ps3\s02\02\130200486.txt
def tryGetSevenZipFilecountAndFileNameString(sevenZipStatusUpdateString):
	# type: (str) -> str
	#NOTE: 'match' is used here, not 'search'
	match = SevenZipStatusUpdate.regexSevenZipFileCountAndName.match(sevenZipStatusUpdateString)
	if not match or len(match.groups()) < 1:
		return None

	return match.groups()[0]

def tryGetOverallStatus(overallStatusString):
	match = SeventhModStatusUpdate.regexSeventhModStatus.search(overallStatusString)
	if not match or len(match.groups()) < 2:
		return None

	return SeventhModStatusUpdate(overallPercentage=int(match.group(1)), currentTask=match.group(2))

# Print a status update which will be recognized by the command line parser
def printSeventhModStatusUpdate(overallPercentage, currentTask):
	# type: (int, str) -> None
	print("<<< Status: {}% [[{}]] >>>".format(overallPercentage, currentTask))
