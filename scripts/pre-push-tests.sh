#!/bin/sh

# exit when any command fails
set -e

GREEN='\033[0;32m'


ruff .
echo "${GREEN}ruff: \t\t OK"

codespell gajim
echo "${GREEN}codespell: \t OK"

pyright
echo "${GREEN}pyright: \t OK"

echo "${GREEN}ready to push"
