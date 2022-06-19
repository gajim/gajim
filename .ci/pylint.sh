#!/bin/sh

# exit when any command fails
set -e

PYLINT=${PYLINT:-pylint}

# Ignore but need fixing

# C0103 invalid-name
# C0415 import-outside-toplevel
# R1710 inconsistent-return-statements
# W0201 attribute-defined-outside-init
# W0221 arguments-differ
# W0233 non-parent-init-called
# W0613 unused-argument

NEED_FIXING=C0103,C0415,R1710,W0201,W0221,W0233,W0613


"$PYLINT" --version
"$PYLINT" --disable="$NEED_FIXING" --ignore=modules,dbus "$@"
"$PYLINT" --disable="C0415" "$@/common/modules"
"$PYLINT" "$@/common/dbus"
