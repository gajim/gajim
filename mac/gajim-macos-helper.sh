#!/bin/bash
#
# Helper script to build virtual environments for nbxmpp and Gajim on Mac OS
#
# Requirements for this script:
# - Brew: Follow installation instructions at https://brew.sh
#
# Instructions:
# - Always check the following versions variables (check tags dates on Gitlab to make nbxmpp and Gajim versions match)
# - Always execute this script from the directory where it is located (./gajim-macos-helper.sh)
# - To build (or rebuild) a new version of nbxmpp and Gajim: ./gajim-macos-helper.sh build
# - To start built version: ./gajim-macos-helper.sh start
# - To create a dmg file (experimental): ./gajim-macos-helper.sh create-dmg
#
# Note: Bash on MacOS is stuck in version 3.2, so we avoid using recent things in this script

set -e

# Variables
gajim_version="2.4.1"
nbxmpp_version="7.0.0"
python_version="3.13"
gajim_git="https://dev.gajim.org/gajim/gajim"
nbxmpp_git="https://dev.gajim.org/gajim/python-nbxmpp"

# Set PATH and DYLD_LIBRARY_PATH for Brew to use Brew Python version (see https://dev.gajim.org/gajim/gajim/-/issues/12365)
DEFAULT_PATH="$PATH"
DEFAULT_DYLD_LIBRARY_PATH="$DYLD_LIBRARY_PATH"
DEFAULT_XDG_DATA_DIRS="$XDG_DATA_DIRS"
if [ "$(uname -m)" == "x86_64" ]
then
	export PATH="/usr/local/bin:$PATH"
	export XDG_DATA_DIRS="/usr/local/share:$XDG_DATA_DIRS"
	export DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH"
elif [ "$(uname -m)" == "arm64" ]
then
	export PATH="/opt/homebrew/bin:$PATH"
	export XDG_DATA_DIRS="/opt/homebrew/share:$XDG_DATA_DIRS"
	export DYLD_LIBRARY_PATH="/opt/homebrew/lib:$DYLD_LIBRARY_PATH"
fi

function install_brew_dependencies() {
	brew install gettext python@${python_version} librsvg git
	brew unlink python && brew link python@${python_version}
	brew install gtk4 libadwaita pygobject3 adwaita-icon-theme libsoup@3 gst-python gtksourceview5 gstreamer
	brew unlink gettext && brew link gettext
	brew unlink libsoup && brew link libsoup@3
	# Reinstall glib via Brew to avoid missing libgobject (see https://github.com/libvips/ruby-vips/issues/284#issuecomment-2040414765)
	brew reinstall glib
	brew unlink glib && brew link glib
}

function recreate_venv() {
	if [ -d "./gajim-venv" ]; then
		rm -r ./gajim-venv
	fi
	python${python_version} -m venv ./gajim-venv
	source ./gajim-venv/bin/activate
	pip3 install --upgrade omemo-dr pyobjc cryptography pillow idna precis-i18n certifi css-parser keyring packaging qrcode SQLAlchemy emoji h2 socksio httpx
	deactivate
}

function clone_source() {
	if [ -d "./gajim-source" ]; then
		rm -rf ./gajim-source
	fi
	if [ -d "./nbxmpp-source" ]; then
		rm -rf ./nbxmpp-source
	fi
	git clone ${gajim_git} ./gajim-source
	git clone ${nbxmpp_git} ./nbxmpp-source
	cd ./nbxmpp-source/
	git checkout ${nbxmpp_version}
	cd ../gajim-source/
	git checkout ${gajim_version}
	cd ../
}

function install_nbxmpp() {
	source ./gajim-venv/bin/activate
	cd ./nbxmpp-source/
	pip3 install .
	cd ../
	deactivate
}

function install_gajim() {
	source ./gajim-venv/bin/activate
	cd ./gajim-source/
	pip3 install .
	cd ../
	deactivate
}

function start_gajim() {
	source ./gajim-venv/bin/activate
	cd ./gajim-source/
	python3 launch.py
	deactivate
}

function clean_environment() {
	if [ -d "./gajim-source" ]; then
		rm -rf ./gajim-source
	fi
	if [ -d "./nbxmpp-source" ]; then
		rm -rf ./nbxmpp-source
	fi
	if [ -d "./gajim-venv" ]; then
		rm -r ./gajim-venv
	fi
}

function build_new_environment() {
	install_brew_dependencies
	recreate_venv
	clone_source
	install_nbxmpp
	install_gajim
}

function create_dmg() {
	source ./gajim-venv/bin/activate
	pip3 install --upgrade PyInstaller
	cd ./gajim-source/
	./mac/makebundle.py
	cd ../
	deactivate
}

function main()
{
	if [ -z "$1" ]
	then
		usage "$0"
	elif [ "$1" == "build" ]
	then
		build_new_environment
	elif [ "$1" == "create-dmg" ]
	then
		create_dmg
	elif [ "$1" == "start" ]
	then
		start_gajim
	elif [ "$1" == "clean" ]
	then
		clean_environment
	fi
}

function usage()
{
	cat <<- EOS
		$1: MacOS Helper to build virtual environments and start Gajim

		build		Build nbxmpp and Gajim virtual environments
		create-dmg	Create Gajim dmg bundle
		start		Start Gajim
		clean		Delete nbxmpp and Gajim virtual environments
	EOS
}

main "$@"

export DYLD_LIBRARY_PATH="$DEFAULT_DYLD_LIBRARY_PATH"
export XDG_DATA_DIRS="$DEFAULT_XDG_DATA_DIRS"
export PATH="$DEFAULT_PATH"

exit 0
