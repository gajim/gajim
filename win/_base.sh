#!/usr/bin/env bash
# Copyright 2016 Christoph Reiter
# Copyright 2017 Philipp Hörist
#
# SPDX-License-Identifier: GPL-2.0-only

set -e

DIR="$( cd "$( dirname "$0" )" && pwd )"
cd "${DIR}"

MAJOR_PY_VERSION="3"
MINOR_PY_VERSION="12"
PYTHON_VERSION="${MAJOR_PY_VERSION}.${MINOR_PY_VERSION}"
BUILD_VERSION="0"

MISC="${DIR}"/misc
PYTHON_ID="python${MAJOR_PY_VERSION}"

QL_VERSION="0.0.0"
QL_VERSION_DESC="UNKNOWN"

MINGW_DEPS="\
${MINGW_PACKAGE_PREFIX}-adwaita-icon-theme \
${MINGW_PACKAGE_PREFIX}-farstream \
${MINGW_PACKAGE_PREFIX}-gst-plugins-base \
${MINGW_PACKAGE_PREFIX}-gst-plugins-good \
${MINGW_PACKAGE_PREFIX}-gst-plugins-bad \
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
${MINGW_PACKAGE_PREFIX}-python-certifi \
${MINGW_PACKAGE_PREFIX}-python-cryptography \
${MINGW_PACKAGE_PREFIX}-python-gobject \
${MINGW_PACKAGE_PREFIX}-python-gssapi \
${MINGW_PACKAGE_PREFIX}-python-idna \
${MINGW_PACKAGE_PREFIX}-python-keyring \
${MINGW_PACKAGE_PREFIX}-python-packaging \
${MINGW_PACKAGE_PREFIX}-python-pillow \
${MINGW_PACKAGE_PREFIX}-python-pip \
${MINGW_PACKAGE_PREFIX}-python-protobuf \
${MINGW_PACKAGE_PREFIX}-python-pygments \
${MINGW_PACKAGE_PREFIX}-python-setuptools \
${MINGW_PACKAGE_PREFIX}-python-setuptools-scm \
${MINGW_PACKAGE_PREFIX}-python-six \
${MINGW_PACKAGE_PREFIX}-python-sqlalchemy \
${MINGW_PACKAGE_PREFIX}-sqlite3 \
${MINGW_PACKAGE_PREFIX}-webp-pixbuf-loader \
"

PYTHON_REQUIREMENTS="\
git+https://dev.gajim.org/gajim/omemo-dr.git
git+https://dev.gajim.org/gajim/python-nbxmpp.git
css_parser
emoji
pystray
python-gnupg
qrcode
sentry-sdk
windows-toasts
winrt-Windows.ApplicationModel~=3.0
winrt-Windows.Foundation~=3.0
winrt-Windows.UI~=3.0
winrt-Windows.UI.ViewManagement~=3.0
"

function set_build_root {
    BUILD_ROOT="${DIR}/_build_root"
    REPO_CLONE="${BUILD_ROOT}/${MSYSTEM_PREFIX:1}"/gajim
    MINGW_ROOT="${BUILD_ROOT}/${MSYSTEM_PREFIX:1}"
    PACKAGE_DIR="${BUILD_ROOT}/${MSYSTEM_PREFIX:1}/lib/python${PYTHON_VERSION}/site-packages"
}

function build_pacman {
    pacman --root "${BUILD_ROOT}" "$@"
}

function build_pip {
    "${BUILD_ROOT}"/"${MSYSTEM_PREFIX:1}"/bin/"${PYTHON_ID}".exe -m pip "$@"
}

function build_python {
    "${BUILD_ROOT}"/"${MSYSTEM_PREFIX:1}"/bin/"${PYTHON_ID}".exe "$@"
}

function build_compileall {
    build_python -m compileall -b "$@"
}

function install_pre_deps {
    pacman -S --needed --noconfirm \
        intltool \
        p7zip \
        wget \
        mingw-w64-x86_64-nsis \
        ${MINGW_PACKAGE_PREFIX}-librsvg \
        ${MINGW_PACKAGE_PREFIX}-python \
        ${MINGW_PACKAGE_PREFIX}-toolchain
}

function create_root {
    mkdir -p "${BUILD_ROOT}"

    mkdir -p "${BUILD_ROOT}"/tmp
    mkdir -p "${BUILD_ROOT}"/var/lib/pacman
    mkdir -p "${BUILD_ROOT}"/var/log

    build_pacman -Syu
    build_pacman --noconfirm -S base
}

function install_mingw_deps {
    build_pacman --noconfirm -S ${MINGW_DEPS}
}

function install_python_deps {
    build_pip install precis-i18n
    build_pip install $(echo "$PYTHON_REQUIREMENTS" | tr ["\\n"] [" "])
}

function post_install_deps {
    # remove the large png icons, they should be used rarely and svg works fine
    rm -Rf "${MINGW_ROOT}/share/icons/Adwaita/512x512"
    rm -Rf "${MINGW_ROOT}/share/icons/Adwaita/256x256"
    rm -Rf "${MINGW_ROOT}/share/icons/Adwaita/96x96"
    rm -Rf "${MINGW_ROOT}/share/icons/Adwaita/64x64"
    rm -Rf "${MINGW_ROOT}/share/icons/Adwaita/48x48"
    "${MINGW_ROOT}"/bin/gtk4-update-icon-cache.exe --force \
        "${MINGW_ROOT}/share/icons/Adwaita"

    # Compile GLib schemas
    "${MINGW_ROOT}"/bin/glib-compile-schemas.exe "${MINGW_ROOT}"/share/glib-2.0/schemas
}

function install_gajim {
    rm -Rf "${PACKAGE_DIR}"/gajim*

    cd ..

    build_python make.py build --dist=win
    build_pip install .

    QL_VERSION=$(MSYSTEM= build_python -c \
        "import gajim; import sys; sys.stdout.write(gajim.__version__.split('+')[0])")

    QL_VERSION_DESC=$(MSYSTEM= build_python -c \
        "import gajim; import sys; sys.stdout.write(gajim.__version__)")

    # Create launchers
    build_python "${MISC}"/create_launcher.py \
        "${QL_VERSION}" "${MINGW_ROOT}"/bin

    # Install language dicts
    curl -o "${BUILD_ROOT}"/speller_dicts.zip https://gajim.org/downloads/snap/win/build/speller_dicts.zip
    7z x -o"${MINGW_ROOT}"/share "${BUILD_ROOT}"/speller_dicts.zip

    # Install our own icons
    rm -Rf "${MINGW_ROOT}/share/icons/hicolor"
    cp -r gajim/data/icons/hicolor "${MINGW_ROOT}"/share/icons

    # Update icon cache
    "${MINGW_ROOT}"/bin/gtk4-update-icon-cache.exe --force \
        "${MINGW_ROOT}/share/icons/hicolor"
}

function cleanup_install {
    # Cleanup build directory to minimize setup file size

    build_pacman --noconfirm -Rdd \
        ${MINGW_PACKAGE_PREFIX}-abseil-cpp \
        ${MINGW_PACKAGE_PREFIX}-frei0r-plugins \
        ${MINGW_PACKAGE_PREFIX}-ncurses \
        ${MINGW_PACKAGE_PREFIX}-python-pip \
        ${MINGW_PACKAGE_PREFIX}-shared-mime-info \
        ${MINGW_PACKAGE_PREFIX}-tcl \
        ${MINGW_PACKAGE_PREFIX}-tk \
        || true

    # Remove directories
    rm -Rf "${MINGW_ROOT}"/include
    rm -Rf "${MINGW_ROOT}"/lib/"${PYTHON_ID}".*/test
    rm -Rf "${MINGW_ROOT}"/lib/"${PYTHON_ID}".*/dist-packages/Ogre
    rm -Rf "${MINGW_ROOT}"/lib/cmake
    rm -Rf "${MINGW_ROOT}"/lib/gettext
    rm -Rf "${MINGW_ROOT}"/lib/installed-tests
    rm -Rf "${MINGW_ROOT}"/lib/libthai
    rm -Rf "${MINGW_ROOT}"/lib/mpg123
    rm -Rf "${MINGW_ROOT}"/lib/OGRE
    rm -Rf "${MINGW_ROOT}"/lib/p11-kit
    rm -Rf "${MINGW_ROOT}"/lib/python2.*
    rm -Rf "${MINGW_ROOT}"/lib/ruby
    rm -Rf "${MINGW_ROOT}"/lib/tabset
    rm -Rf "${MINGW_ROOT}"/lib/tcl8
    rm -Rf "${MINGW_ROOT}"/lib/tcl8.6
    rm -Rf "${MINGW_ROOT}"/lib/terminfo
    rm -Rf "${MINGW_ROOT}"/libexec
    rm -Rf "${MINGW_ROOT}"/share/aclocal
    rm -Rf "${MINGW_ROOT}"/share/appdata
    rm -Rf "${MINGW_ROOT}"/share/bash-completion
    rm -Rf "${MINGW_ROOT}"/share/bullet
    rm -Rf "${MINGW_ROOT}"/share/common-lisp
    rm -Rf "${MINGW_ROOT}"/share/dbus-1
    rm -Rf "${MINGW_ROOT}"/share/doc
    rm -Rf "${MINGW_ROOT}"/share/emacs
    rm -Rf "${MINGW_ROOT}"/share/ffmpeg
    rm -Rf "${MINGW_ROOT}"/share/fontconfig
    rm -Rf "${MINGW_ROOT}"/share/gdb
    rm -Rf "${MINGW_ROOT}"/share/gettext
    rm -Rf "${MINGW_ROOT}"/share/gettext-*
    rm -Rf "${MINGW_ROOT}"/share/gir-1.0
    rm -Rf "${MINGW_ROOT}"/share/gnome-shell
    rm -Rf "${MINGW_ROOT}"/share/gtk-doc
    rm -Rf "${MINGW_ROOT}"/share/info
    rm -Rf "${MINGW_ROOT}"/share/libcaca
    rm -Rf "${MINGW_ROOT}"/share/libtool
    rm -Rf "${MINGW_ROOT}"/share/licenses
    rm -Rf "${MINGW_ROOT}"/share/man
    rm -Rf "${MINGW_ROOT}"/share/mime
    rm -Rf "${MINGW_ROOT}"/share/nghttp2
    rm -Rf "${MINGW_ROOT}"/share/OGRE
    rm -Rf "${MINGW_ROOT}"/share/opencv4
    rm -Rf "${MINGW_ROOT}"/share/pixmaps
    rm -Rf "${MINGW_ROOT}"/share/readline
    rm -Rf "${MINGW_ROOT}"/share/terminfo
    rm -Rf "${MINGW_ROOT}"/share/tessdata
    rm -Rf "${MINGW_ROOT}"/share/vala
    rm -Rf "${MINGW_ROOT}"/share/vulkan
    rm -Rf "${MINGW_ROOT}"/share/xml/docbook
    rm -Rf "${MINGW_ROOT}"/share/zsh
    rm -Rf "${MINGW_ROOT}"/var

    find "${MINGW_ROOT}"/lib/"${PYTHON_ID}".* -type d -name "test*" \
        -prune -exec rm -rf {} \;
    find "${MINGW_ROOT}"/lib/"${PYTHON_ID}".* -type d -name "*_test*" \
        -prune -exec rm -rf {} \;

    # Remove translations we don't support
    for d in "${MINGW_ROOT}"/share/locale/*/LC_MESSAGES; do
        if [ ! -f "${d}"/gajim.mo ]; then
            rm -Rf "${d}"
        fi
    done

    # Remove EXE files
    echo "Removing .exe files"
    RETAINED_EXES="gajim|gajim-debug|python3|gdbus|gspawn-win64-helper"
    find "${MINGW_ROOT}" -regextype "posix-extended" -name "*.exe" -and ! \
        -iregex ".*/(${RETAINED_EXES})\.exe" -exec rm -f {} \; -print

    # Remove individual files
    rm -f "${MINGW_ROOT}"/bin/libBulletCollision.dll
    rm -f "${MINGW_ROOT}"/bin/libBulletDynamics.dll
    rm -f "${MINGW_ROOT}"/bin/libharfbuzz-icu-0.dll
    rm -f "${MINGW_ROOT}"/bin/libopencv_*
    rm -f "${MINGW_ROOT}"/bin/Ogre*
    rm -f "${MINGW_ROOT}"/bin/xvidcore.dll
    rm -f "${MINGW_ROOT}"/lib/gstreamer-1.0/libgstvpx.dll
    rm -f "${MINGW_ROOT}"/lib/gstreamer-1.0/libgstdaala.dll
    rm -f "${MINGW_ROOT}"/lib/gstreamer-1.0/libgstdvdread.dll
    rm -f "${MINGW_ROOT}"/lib/gstreamer-1.0/libgstopenal.dll
    rm -f "${MINGW_ROOT}"/lib/gstreamer-1.0/libgstopenexr.dll
    rm -f "${MINGW_ROOT}"/lib/gstreamer-1.0/libgstresindvd.dll
    rm -f "${MINGW_ROOT}"/lib/gstreamer-1.0/libgstassrender.dll
    rm -f "${MINGW_ROOT}"/lib/gstreamer-1.0/libgstmxf.dll
    rm -f "${MINGW_ROOT}"/lib/gstreamer-1.0/libgstfaac.dll
    rm -f "${MINGW_ROOT}"/lib/gstreamer-1.0/libgstschro.dll
    rm -f "${MINGW_ROOT}"/lib/gstreamer-1.0/libgstcacasink.dll
    # Crashes often on Windows machines
    rm -f "${MINGW_ROOT}"/lib/gstreamer-1.0/libgstamfcodec.dll
    rm -f "${MINGW_ROOT}"/lib/"${PYTHON_ID}".*/lib-dynload/_tkinter*

    # Remove files by rules
    find "${MINGW_ROOT}"/bin -name "*-config" -exec rm -f {} \;
    find "${MINGW_ROOT}"/bin -name "*.pyc" -exec rm -f {} \;
    find "${MINGW_ROOT}"/bin -name "*.pyo" -exec rm -f {} \;
    find "${MINGW_ROOT}"/bin -name "easy_install*" -exec rm -f {} \;
    # This file is not able to compile because of syntax errors
    find "${MINGW_ROOT}"/bin -name "glib-gettextize-script.py" -exec rm -f {} \;

    find "${MINGW_ROOT}" -regex ".*/bin/[^.]+" -exec rm -f {} \; -print
    find "${MINGW_ROOT}" -regex ".*/bin/[^.]+\\.[0-9]+" -exec rm -f {} \; -print

    find "${MINGW_ROOT}"/share/glib-2.0 -type f ! -name "*.compiled" -exec rm -f {} \;

    find "${MINGW_ROOT}" -name ".gitignore" -exec rm -f {} \;
    find "${MINGW_ROOT}" -name "gettext-tools.mo" -exec rm -rf {} \;
    find "${MINGW_ROOT}" -name "old_root.pem" -exec rm -rf {} \;
    find "${MINGW_ROOT}" -name "pylint.rc" -exec rm -f {} \;
    find "${MINGW_ROOT}" -name "weak.pem" -exec rm -rf {} \;

    find "${MINGW_ROOT}" -name "*.a" -exec rm -f {} \;
    find "${MINGW_ROOT}" -name "*.am" -exec rm -f {} \;
    find "${MINGW_ROOT}" -name "*.cmake" -exec rm -f {} \;
    find "${MINGW_ROOT}" -name "*.cmd" -exec rm -f {} \;
    find "${MINGW_ROOT}" -name "*.def" -exec rm -f {} \;
    find "${MINGW_ROOT}" -name "*.desktop" -exec rm -f {} \;
    find "${MINGW_ROOT}" -name "*.h" -exec rm -f {} \;
    find "${MINGW_ROOT}" -name "*.jar" -exec rm -f {} \;
    find "${MINGW_ROOT}" -name "*.la" -exec rm -f {} \;
    find "${MINGW_ROOT}" -name "*.manifest" -exec rm -f {} \;
    find "${MINGW_ROOT}" -name "*.pc" -exec rm -f {} \;
    find "${MINGW_ROOT}" -name "*.pyo" -exec rm -f {} \;
    find "${MINGW_ROOT}" -name "*.sh" -exec rm -f {} \;
    find "${MINGW_ROOT}" -name "*.whl" -exec rm -f {} \;

    find "${MINGW_ROOT}" -type d -name "__pycache__" -prune -exec rm -rf {} \;
    find "${MINGW_ROOT}"/bin -name "*.pyc" -exec rm -f {} \;

    echo "Run depcheck.py"
    build_python "${MISC}/depcheck.py"

    find "${MINGW_ROOT}" -type d -empty -delete
}

function makeappx {
    "$(find /c/Program\ Files\ \(x86\)/Windows\ Kits/10/bin/*/x64/ -name makeappx.exe -print | sort | tail -n 1)" "$@"
}

function makepri {
    "$(find /c/Program\ Files\ \(x86\)/Windows\ Kits/10/bin/*/x64/ -name makepri.exe -print | sort | tail -n 1)" "$@"
}

function build_exe_installer {
    MSYSTEM='MINGW64' /usr/bin/bash -lc "cd ${BUILD_ROOT} && makensis -NOCD -DVERSION=\"$QL_VERSION_DESC\" -DARCH=\"${MSYSTEM_CARCH}\" -DPREFIX=\"${MSYSTEM_PREFIX:1}\" ${MISC}/gajim.nsi"
    MSYSTEM='MINGW64' /usr/bin/bash -lc "cd ${BUILD_ROOT} && makensis -NOCD -DVERSION=\"$QL_VERSION_DESC\" -DARCH=\"${MSYSTEM_CARCH}\" -DPREFIX=\"${MSYSTEM_PREFIX:1}\" ${MISC}/gajim-portable.nsi"
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
                rsvg-convert -w ${scaled_size} -h ${scaled_size} -o assets/gajim${size}x${size}.scale-${scale}.png ${DIR}/../gajim/data/icons/hicolor/scalable/apps/gajim.svg
                echo "\"assets/gajim${size}x${size}.scale-${scale}.png\" \"assets/gajim${size}x${size}.scale-${scale}.png\"" >> filemapping.txt
            done
        done
        for size in {16,24,32,48,256}; do
            rsvg-convert -w ${size} -h ${size} -o assets/gajim44x44.targetsize-${size}.png ${DIR}/../gajim/data/icons/hicolor/scalable/apps/gajim.svg
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
