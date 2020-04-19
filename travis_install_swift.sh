#!/bin/bash

sudo apt-get install clang libicu-dev

SWIFT_TGZ="https://swift.org/builds/swift-5.2.2-release/ubuntu1604/swift-5.2.2-RELEASE/swift-5.2.2-RELEASE-ubuntu16.04.tar.gz"
echo "Downloading $SWIFT_TGZ..."
curl "$SWIFT_TGZ" | sudo tar xzf - --strip-components=1 -C /