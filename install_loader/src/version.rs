pub fn travis_tag() -> &'static str {
	return option_env!("TRAVIS_TAG").unwrap_or("NO_TRAVIS_TAG_SET")
}
