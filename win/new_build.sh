#!/usr/bin/env bash

# Copyright 2016 Christoph Reiter
# Copyright 2017 Philipp Hörist
#
# SPDX-License-Identifier: GPL-2.0-only

set -e

DIR="$( cd "$( dirname "$0" )" && pwd )"
cd "${DIR}"

export PIP_BREAK_SYSTEM_PACKAGES=1

MAJOR_PY_VERSION="3"
MINOR_PY_VERSION="14"
PYTHON_VERSION="${MAJOR_PY_VERSION}.${MINOR_PY_VERSION}"
BUILD_VERSION="0"

MISC="${DIR}"/misc
PYTHON_ID="python${MAJOR_PY_VERSION}"

QL_VERSION="0.0.0"
QL_VERSION_DESC="UNKNOWN"

MINGW_DEPS="\
${MINGW_PACKAGE_PREFIX}-adwaita-icon-theme \
${MINGW_PACKAGE_PREFIX}-gst-plugins-base \
${MINGW_PACKAGE_PREFIX}-gst-plugins-good \
${MINGW_PACKAGE_PREFIX}-gst-plugins-bad \
${MINGW_PACKAGE_PREFIX}-gst-plugins-rs \
${MINGW_PACKAGE_PREFIX}-gst-libav \
${MINGW_PACKAGE_PREFIX}-gst-python \
${MINGW_PACKAGE_PREFIX}-gstreamer \
${MINGW_PACKAGE_PREFIX}-gtk4 \
${MINGW_PACKAGE_PREFIX}-gtksourceview5 \
${MINGW_PACKAGE_PREFIX}-hunspell \
${MINGW_PACKAGE_PREFIX}-libadwaita \
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
${MINGW_PACKAGE_PREFIX}-webp-pixbuf-loader \
"

function install_pre_deps {
    pacman -S --needed --noconfirm \
        intltool \
        p7zip \
        ${MINGW_PACKAGE_PREFIX}-wget \
        ${MINGW_PACKAGE_PREFIX}-nsis \
        ${MINGW_PACKAGE_PREFIX}-librsvg \
        ${MINGW_PACKAGE_PREFIX}-python \
        ${MINGW_PACKAGE_PREFIX}-python-pip \
        ${MINGW_PACKAGE_PREFIX}-toolchain
}

function install_mingw_deps {
    # Downgrade pango https://gitlab.com/gajim/gajim/-/work_items/12730
    pacman --noconfirm -U https://repo.msys2.org/mingw/ucrt64/mingw-w64-ucrt-x86_64-pango-1.56.4-3-any.pkg.tar.zst
    pacman --noconfirm -S ${MINGW_DEPS}
}

function install_python_deps {
    pip install python-gnupg  # for the gpg plugin
}

function install_gajim {
    python make.py build --dist=win
    pip .[sentry,distro] --group=source

    QL_VERSION=$(MSYSTEM= python -c \
        "import gajim; import sys; sys.stdout.write(gajim.__version__.split('+')[0])")

    if [ -n "$APPVEYOR_BUILD_VERSION" ] ; then
        QL_VERSION=${APPVEYOR_BUILD_VERSION}
    fi

    echo "Determined ProductVersion: ${QL_VERSION}"

    QL_VERSION_DESC=$(MSYSTEM= python -c \
        "import gajim; import sys; sys.stdout.write(gajim.__version__)")
}

function makeappx {
    "$(find /c/Program\ Files\ \(x86\)/Windows\ Kits/10/bin/*/x64/ -name makeappx.exe -print | sort | tail -n 1)" "$@"
}

function makepri {
    "$(find /c/Program\ Files\ \(x86\)/Windows\ Kits/10/bin/*/x64/ -name makepri.exe -print | sort | tail -n 1)" "$@"
}

function build_exe_installer {
    cd ${BUILD_ROOT} && makensis -NOCD -DVERSION=${QL_VERSION_DESC} -DARCH=${MSYSTEM_CARCH} -DPREFIX=${MSYSTEM_PREFIX:1} ${MISC}/gajim.nsi
    cd ${BUILD_ROOT} && makensis -NOCD -DVERSION=${QL_VERSION_DESC} -DARCH=${MSYSTEM_CARCH} -DPREFIX=${MSYSTEM_PREFIX:1} ${MISC}/gajim-portable.nsi
}

function build_msix_installer {
    (
        cd ${BUILD_ROOT}

        rm -rf assets bundle filemapping.txt assets.resfiles appxmanifest.xml resources.pri
        echo "[Files]" > filemapping.txt
        find ${MSYSTEM_PREFIX:1} -type f | while read line; do
            echo "\"$line\" \"${line/${MSYSTEM_PREFIX:1}\///}\"" >> filemapping.txt
        done
        mkdir -p assets bundle
        # https://learn.microsoft.com/en-us/windows/apps/design/style/iconography/app-icon-construction
        for size in {44,50,150}; do
            for scale in {100,125,150,200,400}; do
                scaled_size=$(( (${size}*${scale}+100/2)/100 ))
                rsvg-convert -w ${scaled_size} -h ${scaled_size} -o assets/gajim${size}x${size}.scale-${scale}.png ${DIR}/../src/gajim/data/icons/hicolor/scalable/apps/gajim.svg
                echo "\"assets/gajim${size}x${size}.scale-${scale}.png\" \"assets/gajim${size}x${size}.scale-${scale}.png\"" >> filemapping.txt
            done
        done
        for size in {16,24,32,48,256}; do
            rsvg-convert -w ${size} -h ${size} -o assets/gajim44x44.targetsize-${size}.png ${DIR}/../src/gajim/data/icons/hicolor/scalable/apps/gajim.svg
            cp assets/gajim44x44.targetsize-${size}.png assets/gajim44x44.targetsize-${size}_altform-unplated.png
            cp assets/gajim44x44.targetsize-${size}.png assets/gajim44x44.targetsize-${size}_altform-lightunplated.png
            echo "\"assets/gajim44x44.targetsize-${size}.png\" \"assets/gajim44x44.targetsize-${size}.png\"" >> filemapping.txt
            echo "\"assets/gajim44x44.targetsize-${size}_altform-unplated.png\" \"assets/gajim44x44.targetsize-${size}_altform-unplated.png\"" >> filemapping.txt
            echo "\"assets/gajim44x44.targetsize-${size}_altform-lightunplated.png\" \"assets/gajim44x44.targetsize-${size}_altform-lightunplated.png\"" >> filemapping.txt
        done
        sed "s/QL_VERSION/${QL_VERSION}.0/" ${MISC}/appxmanifest.xml > AppxManifest.xml
        makepri new -pr . -cf ${MISC}/priconfig.xml -mn AppxManifest.xml -of resources.pri -o
        echo "\"resources.pri\" \"resources.pri\"" >> filemapping.txt
        echo "\"AppxManifest.xml\" \"AppxManifest.xml\"" >> filemapping.txt
        makeappx pack -f filemapping.txt -p bundle/Gajim_x64.msix -o
        makeappx bundle -d bundle/ -p Gajim.msixbundle -o
    )
}

function unpack_msixbundle {
    (
        cd ${BUILD_ROOT}
        mkdir -p "${BUILD_ROOT}"/unpack
        makeappx unbundle -p Gajim.msixbundle -d "${BUILD_ROOT}"/unpack
        makeappx unpack -p "${BUILD_ROOT}"/unpack/Gajim_x64.msix -d "${BUILD_ROOT}"/unpack/Gajim
        echo Unpacked msixbundle to "${BUILD_ROOT}"/unpack/Gajim
    )
}
