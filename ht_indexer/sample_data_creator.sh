#!/usr/bin/env bash

Checking out into $PWD

GIT_BASE="https://github.com/hathitrust"

echo
echo
echo 📥 Cloning repositories via $GIT_BASE...
echo

git clone --recurse-submodules $GIT_BASE/imgsrv-sample-data ../sample_data/