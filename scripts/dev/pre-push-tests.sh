#!/bin/sh

# exit when any command fails
set -e

GREEN='\033[0;32m'


./scripts/dev/pylint-ci.sh gajim
echo "${GREEN}pylint: \t OK"
mypy gajim
echo "${GREEN}mypy: \t\t OK"
codespell -I codespell.conf --skip="*__pycache__*,gajim/data/icons,gajim/data/sounds,gajim/data/emoticons" gajim
echo "${GREEN}codespell: \t OK"
echo "${GREEN}ready to push"
