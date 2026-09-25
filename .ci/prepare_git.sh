#!/bin/sh

# SPDX-FileCopyrightText: NONE
#
# SPDX-License-Identifier: CC0-1.0

echo "$2" | tr -d '\r' | ssh-add - > /dev/null
ssh-add -l
mkdir -p ~/.ssh
chmod 700 ~/.ssh
ssh-keyscan "$1" >> ~/.ssh/known_hosts
git config --global user.email "$CI_GIT_USER_EMAIL"
git config --global user.name "$CI_GIT_USER_USERNAME"
