import concurrent.futures
import io
import json
from collections import OrderedDict

import common
import installConfiguration

def generateCachedDownloadSizes():
	#setup globals necessary for download
	common.Globals.scanForExecutables()

	modList = common.getModList("installData.json", isURL=False)

	subModconfigList = []
	for mod in modList:
		for submod in mod['submods']:
			conf = installConfiguration.SubModConfig(mod, submod)
			subModconfigList.append(conf)

	# Extract all URLs from the JSON file
	allURLsSet = OrderedDict()
	for submod in subModconfigList:
		print(submod)

		print("files:")
		for file in submod.files:
			print(file.url)
			allURLsSet[file.url] = None

		print("overrides:")
		for fileOverride in submod.fileOverrides:
			print(fileOverride.url)
			allURLsSet[fileOverride.url] = None

		for option in submod.modOptions:
			if option.type == 'downloadAndExtract':
				if option.data is not None:
					print(option.data['url'])
					allURLsSet[option.data['url']] = None

	print("\n\n")

	allURLs = [x for x in allURLsSet.keys() if x is not None]

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
