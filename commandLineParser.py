import re

class AriaStatusUpdate:
	regexAriaCompletionStatus = re.compile(r"\[#[0-9a-zA-Z]+\s([^/]+/[^/]+)\((\d)%\)")
	regexAriaETA = re.compile(r"ETA:([^\]]+)")

	def __init__(self, amountCompletedString, percentCompleted, ETAString):
		self.amountCompletedString = amountCompletedString
		self.percentCompleted = percentCompleted
		self.ETAString = ETAString

# parse a line like: [#7f0d78 27MiB/910MiB(3%) CN:8 DL:4.2MiB ETA:3m27s]
#                or: [#99893f 1.1MiB/910MiB(0%) CN:8 DL:1.1MiB ETA:12m50s]
def tryGetAriaStatusUpdate(ariaStatusUpdateString):
	# type: (str) -> AriaStatusUpdate
	match = AriaStatusUpdate.regexAriaCompletionStatus.search(ariaStatusUpdateString)
	if not match or len(match.groups()) < 2:
		return None

	amountCompletedString = match[1]
	percentCompleted = match[2]

	match = AriaStatusUpdate.regexAriaETA.search(ariaStatusUpdateString)
	if not match or len(match.groups()) < 1:
		return None

	ETAString = match[1]

	return AriaStatusUpdate(amountCompletedString, percentCompleted, ETAString)