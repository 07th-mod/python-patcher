setlocal

echo For development, please make sure to run the script "travis_build_script.py", so it can generate the .xz archive. The script WILL ERROR when it tries to compile the rust file, which is fine as we just want the .xz archive

SET TRAVIS_TAG=v0.0.0.1
cargo check --release

endlocal