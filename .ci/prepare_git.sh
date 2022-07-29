#!/bin/bash

eval $(ssh-agent -s)
echo "$2" | tr -d '\r' | ssh-add - > /dev/null
mkdir -p ~/.ssh
chmod 700 ~/.ssh
ssh-keyscan "$1" >> ~/.ssh/known_hosts
git config --global user.email "$CI_GIT_USER_EMAIL"
git config --global user.name "$CI_GIT_USER_USERNAME"
