#!/usr/bin/env bash

# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

set -e

BUILD_VERSION=$(git rev-list --count HEAD)
APP_VERSION=$(git describe --tags --abbrev=0)

FILE_VERSION_STRING=$APP_VERSION.$BUILD_VERSION
FILE_VERSION_FIXED=${FILE_VERSION_STRING//./, }

PROD_VERSION_STRING=$APP_VERSION.0
PROD_VERSION_FIXED=${PROD_VERSION_STRING//./, }

PLATFORM_DIR=platform/win
BUILD_DIR=build
PYI_BUILD_DIR=$BUILD_DIR/pyinstaller
MSIX_BUILD_DIR=$BUILD_DIR/msix
DIST_DIR=dist/win


export PIP_BREAK_SYSTEM_PACKAGES=1

function install_mingw_deps {
    pacman -S --needed --noconfirm \
        intltool \
        p7zip \
        ${MINGW_PACKAGE_PREFIX}-wget \
        ${MINGW_PACKAGE_PREFIX}-nsis \
        ${MINGW_PACKAGE_PREFIX}-librsvg \
        ${MINGW_PACKAGE_PREFIX}-python \
        ${MINGW_PACKAGE_PREFIX}-python-pip \
        ${MINGW_PACKAGE_PREFIX}-toolchain

    pacman --noconfirm -S \
        ${MINGW_PACKAGE_PREFIX}-adwaita-icon-theme \
        ${MINGW_PACKAGE_PREFIX}-gst-plugins-base \
        ${MINGW_PACKAGE_PREFIX}-gst-plugins-good \
        ${MINGW_PACKAGE_PREFIX}-gst-plugins-bad \
        ${MINGW_PACKAGE_PREFIX}-gst-plugins-rs \
        ${MINGW_PACKAGE_PREFIX}-gst-libav \
        ${MINGW_PACKAGE_PREFIX}-gst-python \
        ${MINGW_PACKAGE_PREFIX}-gstreamer \
        ${MINGW_PACKAGE_PREFIX}-gtksourceview5 \
        ${MINGW_PACKAGE_PREFIX}-hunspell \
        ${MINGW_PACKAGE_PREFIX}-libavif \
        ${MINGW_PACKAGE_PREFIX}-libheif \
        ${MINGW_PACKAGE_PREFIX}-libnice \
        ${MINGW_PACKAGE_PREFIX}-libspelling \
        ${MINGW_PACKAGE_PREFIX}-libsoup3 \
        ${MINGW_PACKAGE_PREFIX}-libwebp \
        ${MINGW_PACKAGE_PREFIX}-python-cryptography \
        ${MINGW_PACKAGE_PREFIX}-python-gobject \
        ${MINGW_PACKAGE_PREFIX}-python-gssapi \
        ${MINGW_PACKAGE_PREFIX}-python-idna \
        ${MINGW_PACKAGE_PREFIX}-python-keyring \
        ${MINGW_PACKAGE_PREFIX}-python-packaging \
        ${MINGW_PACKAGE_PREFIX}-python-pillow \
        ${MINGW_PACKAGE_PREFIX}-python-pip \
        ${MINGW_PACKAGE_PREFIX}-python-protobuf \
        ${MINGW_PACKAGE_PREFIX}-python-sqlalchemy \
        ${MINGW_PACKAGE_PREFIX}-python-pysequoia \
        ${MINGW_PACKAGE_PREFIX}-webp-pixbuf-loader

        # Downgrade pango https://gitlab.com/gajim/gajim/-/work_items/12730
        # https://gitlab.gnome.org/GNOME/pango/-/work_items/905
        pacman --noconfirm -U https://repo.msys2.org/mingw/ucrt64/mingw-w64-ucrt-x86_64-pango-1.56.4-3-any.pkg.tar.zst
        pacman --noconfirm -U https://repo.msys2.org/mingw/ucrt64/mingw-w64-ucrt-x86_64-gtk4-4.22.4-1-any.pkg.tar.zst
        pacman --noconfirm -U https://repo.msys2.org/mingw/ucrt64/mingw-w64-ucrt-x86_64-libadwaita-1.9.3-1-any.pkg.tar.zst
}

function install_python_deps {
    pip install python-gnupg  # for the gpg plugin
    pip install git+https://github.com/pyinstaller/pyinstaller.git
}

function install_gajim {
    python make.py build --dist=win
    pip install .[sentry,distro] --group=source
}


function setup_environment() {
    install_mingw_deps
    install_python_deps
    install_gajim
}

function makeappx {
    "$(find /c/Program\ Files\ \(x86\)/Windows\ Kits/10/bin/*/x64/ -name makeappx.exe -print | sort | tail -n 1)" "$@"
}

function makepri {
    "$(find /c/Program\ Files\ \(x86\)/Windows\ Kits/10/bin/*/x64/ -name makepri.exe -print | sort | tail -n 1)" "$@"
}

function msix_build {

    local PYI_DIST=$PYI_BUILD_DIR/dist
    local BUILD_DIR=$MSIX_BUILD_DIR/build

    rm -rf $MSIX_BUILD_DIR
    mkdir -p $BUILD_DIR

    cp $PLATFORM_DIR/msix/* $MSIX_BUILD_DIR

    local ASSETS=$BUILD_DIR/assets

    mkdir $ASSETS

    echo "Add files from pyinstaller distribution"

    echo "[Files]" > $BUILD_DIR/filemapping.txt
    find $PYI_DIST -type f | while read path; do
        echo "\"$path\" \"${path/$PYI_DIST\//}\"" >> $BUILD_DIR/filemapping.txt
    done

    echo "Create icons"

    # https://learn.microsoft.com/en-us/windows/apps/design/style/iconography/app-icon-construction

    local GAJIM_ICON=src/gajim/data/icons/hicolor/scalable/apps/gajim.svg

    for size in {44,50,150}; do
        for scale in {100,125,150,200,400}; do
            scaled_size=$(( (${size} * ${scale} + 100 / 2) / 100 ))
            rsvg-convert -w ${scaled_size} -h ${scaled_size} -o $ASSETS/gajim${size}x${size}.scale-${scale}.png $GAJIM_ICON
        done
    done

    for size in {16,24,32,48,256}; do
        rsvg-convert -w ${size} -h ${size} -o $ASSETS/gajim44x44.targetsize-${size}.png $GAJIM_ICON
        cp $ASSETS/gajim44x44.targetsize-${size}.png $ASSETS/gajim44x44.targetsize-${size}_altform-unplated.png
        cp $ASSETS/gajim44x44.targetsize-${size}.png $ASSETS/gajim44x44.targetsize-${size}_altform-lightunplated.png
    done

    find $ASSETS -type f | while read path; do
        echo "\"$path\" \"${path/$BUILD_DIR\//}\"" >> $BUILD_DIR/filemapping.txt
    done

    echo "Pack bundle"

    sed -e "s/@PROD_VERSION_STRING@/$PROD_VERSION_STRING/g" $MSIX_BUILD_DIR/AppxManifest.xml.in > $BUILD_DIR/AppxManifest.xml
    echo "\"$BUILD_DIR/AppxManifest.xml\" \"AppxManifest.xml\"" >> $BUILD_DIR/filemapping.txt

    makepri new -pr $BUILD_DIR -cf $MSIX_BUILD_DIR/priconfig.xml -mn $BUILD_DIR/AppxManifest.xml -of $BUILD_DIR/resources.pri -o
    echo "\"$BUILD_DIR/resources.pri\" \"resources.pri\"" >> $BUILD_DIR/filemapping.txt

    makeappx pack -f $BUILD_DIR/filemapping.txt -p $BUILD_DIR/bundle/Gajim_x64.msix -o
    makeappx bundle -d $BUILD_DIR/bundle -p $DIST_DIR/Gajim.msixbundle -o

}

function msix_unpack() {

    if [ -z "$1" ]; then
        echo "Missing path to .msix"
        exit 1
    fi

    if [ -z "$2" ]; then
        echo "Missing destination path"
        exit 1
    fi

    makeappx unbundle -p $1 -d $2/unpack
    makeappx unpack -p $2/unpack/Gajim_x64.msix -d $2/unpack/Gajim
    echo "Unpacked msixbundle to $2/unpack/Gajim"

}

function pyinstaller_build() {

    rm -rf $PYI_BUILD_DIR
    mkdir -p $PYI_BUILD_DIR

    cp -r $PLATFORM_DIR/pyinstaller/* $PYI_BUILD_DIR

    cp $PYI_BUILD_DIR/version.txt.in $PYI_BUILD_DIR/version.txt
    sed -i -e "s/@PROD_VERSION_FIXED@/$PROD_VERSION_FIXED/g" $PYI_BUILD_DIR/version.txt
    sed -i -e "s/@PROD_VERSION_STRING@/$PROD_VERSION_STRING/g" $PYI_BUILD_DIR/version.txt
    sed -i -e "s/@FILE_VERSION_FIXED@/$FILE_VERSION_FIXED/g" $PYI_BUILD_DIR/version.txt
    sed -i -e "s/@FILE_VERSION_STRING@/$FILE_VERSION_STRING/g" $PYI_BUILD_DIR/version.txt

    pyinstaller $PYI_BUILD_DIR/gajim.spec --workpath=$PYI_BUILD_DIR/build --distpath=$PYI_BUILD_DIR

}

function nsis_build() {

    local SOURCE=$PYI_BUILD_DIR/dist
    local RES=$PLATFORM_DIR/nsis
    local OUTPUT=$DIST_DIR

    makensis -NOCD -DVERSION=$APP_VERSION -DSOURCE=$SOURCE -DRESOURCES=$RES -DOUTPUT=$OUTPUT $RES/gajim.nsi
    makensis -NOCD -DSOURCE=$SOURCE -DRESOURCES=$RES -DOUTPUT=$OUTPUT $RES/gajim-portable.nsi

}

function clean() {
        rm -rf $BUILD_DIR
        rm -rf $DIST_DIR
}


function usage()
{
    cat <<- EOS

        $1: Windows helper to build Gajim installer

        setup                   Install all dependencies and Gajim
        build-installer         Create the Gajim installer .exe and .msix
        clean                   Remove the build and dist folder
        unpack-msix FILE DEST   Unpack the .msix to a destination folder
EOS
}

function main()
{

    if [ -z "$1" ]; then
        usage "$0"

    elif [ "$1" == "setup" ]; then
        setup_environment

    elif [ "$1" == "build-installer" ]; then
        # pyinstaller_build
        # msix_build
        nsis_build

    elif [ "$1" == "clean" ]; then
        clean

    elif [ "$1" == "msix-unpack" ]; then
        msix_unpack $2 $3

    else
        echo "Unknown command $1"
        exit 1

    fi

}

main "$@"
