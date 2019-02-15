import os

url_base = r"https://raw.githubusercontent.com/07th-mod/python-patcher/master/"
valid_extensions = {".py", ".gif"}


# get all files which have the ext
with open("scriptDownloadList.txt", "w") as scriptDownloadList:
	for filename in os.listdir("."):
		_, ext = os.path.splitext(filename)
		if ext in valid_extensions and 'developer_' not in filename:
			url = os.path.join(url_base, filename)
			print("Adding [{}]".format(url))
			scriptDownloadList.write(url + "\n")