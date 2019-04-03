import XCTest
import PedanticJSONDecoder
@testable import JSONValidator

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
					for os in OS.allCases {
						for steam in [true, false] {
							if !submod.fileOverrides.contains(where: { override in
								override.name == file.name && override.os.contains(os) && (override.steam ?? steam == steam)
							}) {
								XCTFail("\(mod.name) \(submod.name) \(file.name) must be overridden but a user with the os \(os) and steam \(steam) will have no overrides available")
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
		}
	}

	func testURLsExist() {
		let decoder = PedanticJSONDecoder()
		guard let installData = try? decoder.decode(InstallDataDefinition.self, from: Data(contentsOf: installData)) else {
			XCTFail("Failed to decode install data, look at other tests for details")
			return
		}
		let allURLs = installData.mods.flatMap({ mod -> [String] in
			return mod.submods.flatMap { submod -> [String] in
				return submod.files.compactMap { $0.url } + submod.fileOverrides.map { $0.url }
			}
		}).compactMap { urlString -> URL? in
			let url = URL(string: urlString)
			XCTAssertNotNil(url, "The url \"\(urlString)\" was invalid")
			return url
		}
		for url in Set(allURLs) {
			let e = expectation(description: "\(url) should be retrievable")
			var request = URLRequest(url: url)
			request.setValue("bytes=0-1023", forHTTPHeaderField: "Range")

			var task: URLSessionDataTask? = nil
			task = URLSession.shared.dataTask(with: request) { [weak task] (data, response, error) in
				task?.cancel()
				if let error = error {
					XCTFail("Failed to download \(url): \(error)")
				}
				else if let response = response as? HTTPURLResponse {
					if response.statusCode != 200 && response.statusCode != 206 {
						XCTFail("Failed to download \(url): response code was \(response.statusCode)")
					}
				}
				else if let response = response {
					XCTFail("Failed to download \(url): unexpected response: \(response)")
				}
				else {
					XCTFail("Failed to download \(url): got nil response with no error")
				}
				e.fulfill()
			}
			task!.resume()
		}
		waitForExpectations(timeout: 20)
	}

	static var allTests = [
		("Finds installData.json", testFindInstallData),
		("Validate JSON", testValidateJSON),
		("Ensure all file overrides override something", testOverridesAreValid),
		("Ensure that all URLs actually exist", testURLsExist),
	]
}
