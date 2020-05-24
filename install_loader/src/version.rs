fn get_github_ref() -> Option<&'static str> {
	option_env!("GITHUB_REF")
}

pub fn travis_tag() -> &'static str {
	let github_ref = get_github_ref().unwrap_or("refs/tags/DEVELOPER_BUILD");
	github_ref.rsplit('/').next().unwrap_or(github_ref)
}

pub fn is_developer_build() -> bool {
	get_github_ref().is_none()
}
