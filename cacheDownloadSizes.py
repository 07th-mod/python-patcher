from __future__ import unicode_literals

import concurrent.futures
import io
import json
import typing
from collections import OrderedDict

import common
import installConfiguration

def getAllURLsFromModList(modList, shouldPrint=False):
	# type: (typing.Any, typing.Optional[bool]) -> typing.List[str]
	"""
	This function parses the modList (from common.getModList()), and returns all downloadable URLs contained in it.
	Metalinks are treated as just "one" URL, even if they contain multiple files inside.

	:param modList: JSON modList object from common.getModList()
	:param shouldPrint: Enables/Disables debug printing
	:return: a list of URLs (str) from the modList JSON object
	"""
	if shouldPrint:
		customPrint = print
	else:
		def customPrint(*args, **kwargs):
			pass

	subModconfigList = []
	for mod in modList:
		for submod in mod['submods']:
			conf = installConfiguration.SubModConfig(mod, submod)
			subModconfigList.append(conf)

	# Extract all URLs from the JSON file
	allURLsSet = OrderedDict()
	for submod in subModconfigList:
		customPrint(submod)

		customPrint("files:")
		for file in submod.files:
			customPrint(file.url)
			allURLsSet[file.url] = None

		customPrint("overrides:")
		for fileOverride in submod.fileOverrides:
			customPrint(fileOverride.url)
			allURLsSet[fileOverride.url] = None

		for option in submod.modOptions:
			if option.type == 'downloadAndExtract':
				if option.data is not None:
					customPrint(option.data['url'])
					allURLsSet[option.data['url']] = None

	customPrint("\n\n")

	return [x for x in allURLsSet.keys() if x is not None]

def generateCachedDownloadSizes():
	#setup globals necessary for download
	common.Globals.scanForExecutables()

	modList = common.getModList("installData.json", isURL=False)

	allURLs = getAllURLsFromModList(modList)

	def queryAndPrint(url):
		res = common.DownloaderAndExtractor.getExtractableItem(url, '.')
		return url, res

	# Only works on python 3
	urlToFileSizeDict = {}
	with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
		results = executor.map(queryAndPrint, allURLs)

		for url, extractableItemList in results:
			totalSize = 0
			for extractableItem in extractableItemList:
				totalSize += extractableItem.length
			urlToFileSizeDict[url] = totalSize
			print(url, extractableItemList)

	with io.open('cachedDownloadSizes.json', 'w', encoding='utf-8') as file:
		file.write(json.dumps(urlToFileSizeDict, indent=4, sort_keys=True))


if __name__ == '__main__':
	generateCachedDownloadSizes()
