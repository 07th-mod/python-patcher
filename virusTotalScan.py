import hashlib
import os

import vt  # VirusTotal - pip install vt-py

VT_API_KEY = os.environ.get('VT_API_KEY') # VirusTotal API Key
if VT_API_KEY is None:
	print("ERROR: You must provide a VirusTotal API Key using the environment variable 'VT_API_KEY' for this script to work")
	exit(-1)

def sha256_of_file(file_path):
	BLOCK_SIZE = 65536

	file_hash = hashlib.sha256()
	with open(file_path, 'rb') as f:
		fb = f.read(BLOCK_SIZE)
		while len(fb) > 0:
			file_hash.update(fb)
			fb = f.read(BLOCK_SIZE)

	return file_hash.hexdigest()

def do_scan(api_key, file_path):
	with vt.Client(api_key) as client:
		try:
			file = client.get_object(f"/files/{sha256_of_file(file_path)}")
			stats = file.last_analysis_stats
			results = file.last_analysis_results
		except vt.APIError as e:
			print(f"Uploading file as file not already in database ({e})")
			with open(file_path, "rb") as final_exe_file:
				analysis = client.scan_file(final_exe_file, wait_for_completion=True)
				stats = analysis.stats
				results = analysis.results

		print(stats)
		print("Scanners with positive results:")
		for scanner_name, scanner_result_dict in results.items():
			result = scanner_result_dict["result"]
			if result:
				print(f'- {scanner_name}: {result}')

def scan():
	output_folder = 'travis_installer_output'
	loader_exe_names = ['07th-Mod.Installer.Windows.exe', '07th-Mod.Installer.Windows.SafeMode.exe']

	for exe_name in loader_exe_names:
		final_exe_path = os.path.join(output_folder, exe_name)

		# Scan the .exe with virustotal
		print(f"Beginning VirusTotal Scan of {exe_name}...")
		do_scan(VT_API_KEY, final_exe_path)

if __name__ == '__main__':
	scan()
