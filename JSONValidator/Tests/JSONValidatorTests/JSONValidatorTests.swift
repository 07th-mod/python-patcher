import XCTest
import PedanticJSONDecoder
@testable import JSONValidator
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

let rootDirectory = URL(fileURLWithPath: #file).deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
let installData = rootDirectory.appendingPathComponent("installData.json", isDirectory: false)

extension Array where Element == CodingKey {
	var stringValue: String {
		return map({ $0.stringValue }).joined(separator: " → ")
	}

	var pathString: String {
		let str = stringValue
		return str.isEmpty ? "top level" : "path \(str)"
	}
}

final class JSONValidatorTests: XCTestCase {
	func testFindInstallData() {
		XCTAssertNoThrow(try Data(contentsOf: installData))
	}

	func testValidateJSON() {
		let decoder = PedanticJSONDecoder()
		do {
			_ = try decoder.decode(InstallDataDefinition.self, from: try Data(contentsOf: installData))
		}
		catch let error as PedanticJSONDecoder.IgnoredKeysError {
			let message = error.keysets.map({ keyset -> String in
				return "The keys \(keyset.ignoredKeys) were in installData.json at the \(keyset.path.pathString), but nothing should be there according to the spec in JSONValidator.swift"
			}).joined(separator: "\n")
			XCTFail(message)
		}
		catch let error as DecodingError {
			switch error {
			case .dataCorrupted(let context):
				XCTFail("Something went wrong decoding installData.json at the \(context.codingPath.pathString): \(context.debugDescription)")
			case .keyNotFound(let key, let context):
				XCTFail("According to the spec in JSONValidator.swift, a \"\(key.stringValue)\" key should have been at the \(context.codingPath.pathString) in installData.json, but there wasn't anything there")
			case .valueNotFound(let expectedType, let context):
				XCTFail("According to the spec in JSONValidator.swift, there should have been a \(expectedType) at the \(context.codingPath.pathString), but in installData.json, the value was null instead")
			case .typeMismatch(let expectedType, let context):
				XCTFail("According to the spec in JSONValidator.swift, there should have been a \(expectedType) at the \(context.codingPath.pathString), but the value in installData.json couldn't be converted to that: \(context.debugDescription)")
			}
		}
		catch {
			// Force an assertion failure with the error
			XCTAssertNoThrow(try { throw error }())
		}
	}

	func testOverridesAreValid() {
		let decoder = PedanticJSONDecoder()
		guard let installData = try? decoder.decode(InstallDataDefinition.self, from: Data(contentsOf: installData)) else {
			XCTFail("Failed to decode install data, look at other tests for details")
			return
		}
		for mod in installData.mods {
			for submod in mod.submods {
				for file in submod.files where file.url == nil {
					func isOverrideAvailable(os: OS, steam: Bool) -> Bool {
						return submod.fileOverrides.contains(where: { override in
							return override.name == file.name
							    && override.os.contains(os)
							    && (override.steam ?? steam == steam)
						})
					}

					for os in OS.allCases {
						if isOverrideAvailable(os: os, steam: true) != isOverrideAvailable(os: os, steam: false) {
							if isOverrideAvailable(os: os, steam: true) {
								XCTFail("A user on \(os) will only have \(mod.name) \(submod.name) \(file.name) available if they installed with steam, please add a version for if they don't have steam")
							}
							else {
								XCTFail("A user on \(os) will only have \(mod.name) \(submod.name) \(file.name) available if they installed without steam, please add a version for if they do have steam")
							}
						}
					}
				}
				let files = Set(submod.files.lazy.map { $0.name })
				XCTAssertEqual(files.count, submod.files.count, "Multiple files were specified with the same name in \(mod.name) \(submod.name)")
				for override in submod.fileOverrides {
					XCTAssert(files.contains(override.name), "Override \(override.name) must override a file in the file list of \(mod.name) \(submod.name)")
				}
			}
			for option in mod.modOptionGroups ?? [] {
				let numNonNil = [option.radio, option.checkBox].lazy.filter({ $0 != nil }).count
				if numNonNil != 1 {
					XCTFail("\(mod.name) option \(option.name) must have either a radio button or checkBox but not both")
				}
				if case .downloadAndExtract = option.type {
					option.checkBox?.forEach { XCTAssertNotNil($0.data, "CheckBoxes for 'downloadAndExtract' must have data but \(mod.name) option \(option.name) doesn't!") }
				}
			}
		}
	}

	class URLTester: NSObject, URLSessionDataDelegate {
		var session: URLSession!
		var requests: [URLSessionTask: (req: URLRequest, url: URL, tries: Int, path: String, exp: XCTestExpectation)] = [:]

		override init() {
			super.init()
			let config = URLSessionConfiguration.ephemeral
			config.httpMaximumConnectionsPerHost = 1
			session = URLSession(configuration: config, delegate: self, delegateQueue: .main)
		}

		func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive data: Data) {
			guard dataTask.state != .canceling else { return }
			if dataTask.countOfBytesExpectedToReceive > (1024 * 1024) {
				// Server not honoring range request for a large (multi-megabyte) file!
				let mb = dataTask.countOfBytesExpectedToReceive / (1024 * 1024)
				if let info = requests[dataTask] {
					print("::warning::Server did not honor range request when downloading the \(mb)mb file \(info.url) (path: \(info.path))")
				} else {
					let name = dataTask.currentRequest?.url?.absoluteString ?? "<unknown>"
					print("::warning::Server did not honor range request when downloading the \(mb)mb file \(name)")
				}
				dataTask.cancel()
			}
		}

		func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: Error?) {
			guard let (request, url, tries, codingPath, expectation) = requests[task] else {
				print("Received callback for unregistered task!")
				return
			}
			requests[task] = nil
			if let error = error, (error as NSError).code != NSURLErrorCancelled {
				if tries > 1, (error as NSError).code == NSURLErrorTimedOut {
					// If it times out, try again
					print("Attempt to download \(url) timed out, \(tries - 1) retries left")
					tryDownload(request, fulfilling: expectation, url: url, codingPath: codingPath, tries: tries - 1)
					return
				}
				XCTFail("Failed to download \(url) (at \(codingPath)): \(error)")
			}
			else if let response = task.response as? HTTPURLResponse {
				// Open source Foundation doesn't properly follow HTTP 300s
				if response.statusCode / 100 == 3, let loc = response.allHeaderFields["location"].flatMap({ $0 as? String }).flatMap(URL.init(string:)) {
					var request = request
					request.url = loc
					tryDownload(request, fulfilling: expectation, url: loc, codingPath: codingPath, tries: tries - 1)
					return
				}
				if response.statusCode != 200 && response.statusCode != 206 {
					XCTFail("Failed to download \(url) (at \(codingPath)): response code was \(response.statusCode)")
				}
			}
			else if let response = task.response {
				XCTFail("Failed to download \(url) (at \(codingPath)): unexpected response: \(response)")
			}
			else {
				XCTFail("Failed to download \(url) (at \(codingPath)): got nil response with no error")
			}
			expectation.fulfill()
		}

		/// Attempts to download the given file, fulfilling the given expectation if it succeeds
		/// If the request times out, the download will be retried for a total of up to `tries` tries.
		func tryDownload(
			_ request: URLRequest,
			fulfilling expectation: XCTestExpectation,
			url: URL,
			codingPath: String,
			tries: Int
		) {
			let task = session.dataTask(with: request)
			requests[task] = (request, url, tries, codingPath, expectation)
			task.resume()
		}
	}

	func testURLsExist() {
		let decoder = PedanticJSONDecoder()
		guard let installData = try? decoder.decode(InstallDataDefinition.self, from: Data(contentsOf: installData)) else {
			XCTFail("Failed to decode install data, look at other tests for details")
			return
		}

		let tester = URLTester()

		func testDownload(_ urlString: String, codingPath: String) {
			guard let url = URL(string: urlString) else {
				XCTFail("The url \"\(urlString)\" was invalid")
				return
			}
			let e = expectation(description: "\(url) (at \(codingPath)) is downloadable")
			var request = URLRequest(url: url)
			request.setValue("bytes=0-1023", forHTTPHeaderField: "Range")
			request.timeoutInterval = Double.random(in: 4...6) // Use a random interval so if the timeout reason was that the server didn't like our request spam, subsequent requests will be more and more spread out

			tester.tryDownload(request, fulfilling: e, url: url, codingPath: codingPath, tries: 8)
		}

		for mod in installData.mods {
			for submod in mod.submods {
				for file in submod.files {
					if let url = file.url {
						testDownload(url, codingPath: "\(mod.name) → \(submod.name) → \(file.name)")
					}
				}
				for (index, file) in submod.fileOverrides.enumerated() {
					testDownload(file.url, codingPath: "\(mod.name) → \(submod.name) → override \(index) / \(submod.name)")
				}
			}
			for option in mod.modOptionGroups ?? [] {
				if let entry = option.radio ?? option.checkBox {
					for item in entry where item.data != nil {
						testDownload(item.data!.url, codingPath: "\(mod.name) → option \(option.name) → \(item.name)")
					}
				}
			}
		}

		waitForExpectations(timeout: 60)
	}

	static var allTests = [
		("Finds installData.json", testFindInstallData),
		("Validate JSON", testValidateJSON),
		("Ensure all file overrides override something", testOverridesAreValid),
		("Ensure that all URLs actually exist", testURLsExist),
	]
}
