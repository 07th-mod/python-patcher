public struct InstallDataDefinition: Codable {
	/// Increment this every time a breaking change is made to the installData JSON that would cause earlier versions of the installer to misparse it.
	public var version: Int
	public var mods: [ModDefinition]
}

public struct ModDefinition: Codable {
	public var family: ModFamily
	public var name: String
	public var target: String
	public var dataname: String
	public var identifiers: [String]
	public var submods: [SubmodDefinition]
	/// If this exists and the user is on macOS, the installer will overwrite the CFBundleName of the target application with the name given here.  This will change the name that shows up when the application is launched.
	public var CFBundleName: String?
	/// If this exists and the user is on macOS, the installer will overwrite the CFBundleIdentifier of the target application with the name given here.  This will change the save directory used on Higurashi games.
	public var CFBundleIdentifier: String?
}

public enum ModFamily: String, Codable {
	case higurashi
	case umineko
}

public struct SubmodDefinition: Codable {
	public var name: String
	public var files: [FileDefinition]
	public var fileOverrides: [FileOverrideDefinition]
}

public struct FileDefinition: Codable {
	public var name: String
	public var url: String
	public var priority: Int
}

public struct FileOverrideDefinition: Codable {
	public var name: String
	public var os: [OS]
	public var steam: Bool?
	public var url: String
}

public enum OS: String, Codable {
	case mac
	case linux
	case windows
}
