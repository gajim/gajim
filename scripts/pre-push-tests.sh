#!/bin/sh

# exit when any command fails
set -e

GREEN='\033[0;32m'


pyright
echo "${GREEN}pyright: \t OK"
ruff .
echo "${GREEN}ruff: \t\t OK"
codespell gajim
echo "${GREEN}codespell: \t OK"
echo "${GREEN}ready to push"
