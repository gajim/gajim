#!/bin/bash

# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

# Helper script to build and run Gajim on Mac OS
#
# Requirements for this script:
# - Brew: Follow installation instructions at https://brew.sh
#
# Notes:
# - Always execute this script from the root directory of this repository
# - Run ./mac/gajim-macos_helper.sh to print the help
# - Bash on macOS is stuck in version 3.2, so we avoid using recent things in this script

set -e

# Variables
PYTHON_VERSION="3.14"
VENV_FOLDER="./gajim-venv"
: ${TAG:=0}
: ${GAJIM_CI_BUILD:=0}

# Set PATH and DYLD_LIBRARY_PATH for Brew to use Brew Python version (see https://gitlab.com/gajim/gajim/-/work_items/12365)
DEFAULT_PATH="$PATH"
DEFAULT_DYLD_LIBRARY_PATH="$DYLD_LIBRARY_PATH"
DEFAULT_XDG_DATA_DIRS="$XDG_DATA_DIRS"
if [ "$(uname -m)" == "x86_64" ]
then
    export PATH="/usr/local/bin:/Library/Frameworks/Python.framework/Versions/${PYTHON_VERSION}/bin:$PATH"
    export XDG_DATA_DIRS="/usr/local/share:${XDG_DATA_DIRS}"
    export DYLD_LIBRARY_PATH="/usr/local/lib:${DYLD_LIBRARY_PATH}"
elif [ "$(uname -m)" == "arm64" ]
then
    export PATH="/opt/homebrew/bin:$PATH"
    export XDG_DATA_DIRS="/opt/homebrew/share:${XDG_DATA_DIRS}"
    export DYLD_LIBRARY_PATH="/opt/homebrew/lib:${DYLD_LIBRARY_PATH}"
fi

function python_v() {
    python${PYTHON_VERSION} "$@"
}

function install_brew_dependencies() {
    brew update
    if [ $GAJIM_CI_BUILD == 0 ]; then
        brew install python@${PYTHON_VERSION}
    fi
    brew install gettext librsvg git
    brew unlink python && brew link python@${PYTHON_VERSION}
    brew install gtk4 libadwaita pygobject3 adwaita-icon-theme libsoup@3 gst-python gtksourceview5 gstreamer libspelling
    brew unlink gettext && brew link gettext
    brew unlink libsoup && brew link libsoup@3
    # Reinstall glib via Brew to avoid missing libgobject (see https://github.com/libvips/ruby-vips/issues/284#issuecomment-2040414765)
    brew reinstall glib
    brew unlink glib && brew link glib
}

function activate_env() {
    if [ $GAJIM_CI_BUILD == 0 ]; then
        if [ ! -d $VENV_FOLDER ]; then
           echo ERROR: Virtual environment does not exist. Run "build" first.
           exit 1
        fi
        echo Activate environment
        source ${VENV_FOLDER}/bin/activate
    fi
}

function deactivate_env() {
    if [ $GAJIM_CI_BUILD == 0 ]; then
        echo Deactivate environment
        deactivate
    fi
}

function start_gajim() {
    activate_env
    gajim
    deactivate_env
}

function build_env() {
    install_brew_dependencies

    # Create env if it does not exist
    if [[ ! -d ${VENV_FOLDER} && $GAJIM_CI_BUILD != 0 ]]; then
        echo "Creating environment"
        python_v -m venv ${VENV_FOLDER}
    fi

    if [ $TAG != 0 ]; then
        git checkout $TAG
    fi

    activate_env
    python_v -m pip install git+https://github.com/pyinstaller/pyinstaller.git
    python_v ./make.py build --dist macos
    python_v -m pip install .[sentry,distro] --group=source
    deactivate_env
}

function create_dmg() {
    activate_env
    pyinstaller mac/gajim.spec
    hdiutil create -volname Gajim -srcfolder dist -ov -format UDZO gajim-build.dmg
    deactivate_env
}

function main()
{

    # CI
    if [ $GAJIM_CI_BUILD == 1 ]; then
        export PIP_BREAK_SYSTEM_PACKAGES=1
    fi

    if [ ! -z "$2" ]; then
        TAG="$2"
    fi

    # Selector
    if [ -z "$1" ]; then
        usage "$0"
    elif [ "$1" == "build" ]; then
        build_env
    elif [ "$1" == "create-dmg" ]; then
        create_dmg
    elif [ "$1" == "start" ]; then
        start_gajim
    elif [ "$1" == "clean" ]; then
        rm -r ${VENV_FOLDER}
    fi
}

function usage()
{
    cat <<- EOS

        $1: macOS Helper to build a virtual environment and run Gajim

        build [tag]   Build the virtual environment and install Gajim
        create-dmg    Create the Gajim dmg bundle
        start         Start Gajim
        clean         Remove the virtual environment
EOS
}

main "$@"

export DYLD_LIBRARY_PATH="$DEFAULT_DYLD_LIBRARY_PATH"
export XDG_DATA_DIRS="$DEFAULT_XDG_DATA_DIRS"
export PATH="$DEFAULT_PATH"

exit 0
