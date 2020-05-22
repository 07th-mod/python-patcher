pub fn travis_tag() -> &'static str {
	return option_env!("GITHUB_REF").unwrap_or("NO_GIT_TAG_SET")
}
