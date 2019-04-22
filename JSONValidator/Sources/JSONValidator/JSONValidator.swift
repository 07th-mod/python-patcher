/*
Reading this file (for those not familiar with swift)

Each struct represents one object in JSON.
Each variable name (prefixed with `public var`) is a key in the JSON object, and the thing to the right of the colon is its type.
Types surrounded by `[]`s are arrays of that type, so `[String]` would be an array of strings.
Types with a `?` after them are optional, meaning they can be null (or completely missing from the JSON).

An enum represents a fixed set of strings (for example, the enum `OS` indicates a value that can be either the string "mac", "linux", or "windows" but nothing else)
*/

/// The top level object in `installData.json`
public struct InstallDataDefinition: Codable {
	/// Increment this every time a breaking change is made to the installData JSON that would cause earlier versions of the installer to misparse it.
	public var version: Int
	public var mods: [ModDefinition]
}

/// Represents one mod for a game
///
/// The difference between a mod and a submod is that a user might be expected to have one of each mod installed, but would not be expected to have more than one submod of that mod.
/// Based on that, Himatsubushi and Console Arcs are separate mods (even though they're based on the same game), but a voice only patch and full version would be submods
public struct ModDefinition: Codable {
	/// Used to decide how the installer should run, since higurashi and umineko games have very different layouts
	public var family: ModFamily
	/// The name of the mod (will be displayed to the user)
	public var name: String
	/// The name of the game this mod installs onto
	public var target: String
	/// The name of the folder that contains the game data (e.g. HigurashiEp02_Data)
	public var dataname: String
	/// Filenames that, if found in a folder, indicate that it is the game data folder of this mod's target
	public var identifiers: [String]
	/// The list of submods this mod has
	public var submods: [SubmodDefinition]
	/// A list of selectable mod options that can apply to any submod
	public var modOptionGroups: [ModOptionGroup]?
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
	/// The base set of files for this mod
	public var descriptionID: String
	/// This variable sets which description to display on the web GUI. The actual description text is stored on the webpage, not in the JSON or python side.
	public var files: [FileDefinition]
	/// Platform-specific overrides of files in `files`
	public var fileOverrides: [FileOverrideDefinition]
}

public struct FileDefinition: Codable {
	/// A name to identify this file for use in overrides
	public var name: String
	/// The url for this file
	/// - If null, this file must be overridden or the install will fail
	public var url: String?
	/// The priority of this file.  Higher priority files are installed later so they will overwrite lower priority files
	public var priority: Int
}

public struct FileOverrideDefinition: Codable {
	/// This override will replace a file with the same name
	/// - warning: It is an error to specify a name that is not in the `files` of the submod
	public var name: String
	/// The OSes this override should be applied on
	public var os: [OS]
	/// - If non-null, will apply to the game if they have the given Unity version (Higurashi only)
	/// - If null or missing, will apply always
	public var unity: String?
	/// - If true, this override will only be applied if the game is a steam version.
	/// - If false, this override will only be applied if the game is not a steam version.
	/// - If null, this override will be applied regardless of whether the game is a steam version.
	public var steam: Bool?
	/// The url for this file override
	public var url: String
}

public enum OS: String, Codable, CaseIterable {
	case mac
	case linux
	case windows
}

public struct ModOptionGroup: Codable {
	/// The name of this group
	public var name: String
	/// The type (currently only one option)
	public var type: ModOptionType
	/// Data for if this is a radio button.  Mutually exclusive with checkBox
	public var radio: [ModOptionEntry]?
	/// Data for if this is a checkBox.  Mutually exclusive with radio
	public var checkBox: [ModOptionEntry]?
}

public enum ModOptionType: String, Codable {
	case downloadAndExtract
}

public struct ModOptionEntry: Codable {
	/// The name of this option
	public var name: String
	/// A longer description of the option
	public var description: String
	/// The data to download if this option is selected (null indicates a radio button that is just there to be "not the others" and doesn't actually add anything)
	public var data: ModOptionFileDefinition?
}

public struct ModOptionFileDefinition: Codable {
	/// The url for the mod option
	public var url: String
	/// A path relative to the *top-level game directory* (should contain HigurashiEp##_data for a higurashi game's data folder)
	public var relativeExtractionPath: String
	/// The priority of this file (same system as above priorities)
	public var priority: Int
}
