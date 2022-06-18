#!/bin/sh

# exit when any command fails
set -e

PYLINT=${PYLINT:-pylint}

# Errors which are covered by pyright
#
# E1101 no-member
# E1102 not-callable
# E1111 assignment-from-no-return
# E1120 no-value-for-parameter
# E1121 too-many-function-args
# E1123 unexpected-keyword-arg
# E1124 redundant-keyword-arg
# E1125 missing-kwoa
# E1126 invalid-sequence-index
# E1127 invalid-slice-index
# E1128 assignment-from-none
# E1129 not-context-manager
# E1130 invalid-unary-operand-type
# E1131 unsupported-binary-operation
# E1132 repeated-keyword
# E1133 not-an-iterable
# E1134 not-a-mapping
# E1135 unsupported-membership-test
# E1136 unsubscriptable-object
# E1137 unsupported-assignment-operation
# E1138 unsupported-delete-operation
# E1139 invalid-metaclass
# E1140 unhashable-dict-key
# E1141 dict-iter-missing-items
# E1142 await-outside-async
# I1101 c-extension-no-member
# W0212 protected-access
# W1113 keyword-arg-before-vararg
# W1114 arguments-out-of-order
# W1115 non-str-assignment-to-dunder-name
# W1116 isinstance-second-argument-not-valid-type

IGNORE_FLAKE8='C0301,W0611'

IGNORE_PYRIGHT='E1101,E1102,E1111,E1120,E1121,E1123,E1124,E1125,E1126,E1127,E1128,E1129,E1130,E1131,E1132,E1133,E1134,E1135,E1136,E1137,E1138,E1139,E1140,E1141,E1142,I1101,W0212,W1113,W1114,W1115,W1116'

IGNORE_ALWAYS='R0801,C0209,W0237,W0707,R1732,W1404,W1406,R1725'

IGNORE_ERRORS=C0103,C0302,C0301,C0330,C0411,C0415,E0401,E0611,R0201,R0901,R0904,R0912,R0913,R0914,R0915,R0916,R1702,R1710,W0201,W0221,W0223,W0231,W0233,W0603,W0613

IGNORE_GTK_MODULE_ERRORS=C0103,C0301,C0330,C0415,E0401,E0611,R0201,R0904,R0915,R1710,W0201,W0233,W0221,W0613

"$PYLINT" --version

"$PYLINT" --disable="$IGNORE_PYRIGHT,$IGNORE_ALWAYS,$IGNORE_FLAKE8,$IGNORE_ERRORS" --ignore=modules,dbus,gtk "$@"
"$PYLINT" --disable="$IGNORE_PYRIGHT,$IGNORE_ALWAYS,$IGNORE_FLAKE8,$IGNORE_GTK_MODULE_ERRORS" "$@/gtk"
"$PYLINT" --disable="$IGNORE_PYRIGHT,$IGNORE_ALWAYS,$IGNORE_FLAKE8,E0401,C0415" "$@/common/modules"
"$PYLINT" --disable="$IGNORE_PYRIGHT,$IGNORE_ALWAYS,$IGNORE_FLAKE8," "$@/common/dbus"

# C0103 invalid-name
# C0209 use-f-string
# C0301 line-too-long
# C0302 too-many-lines
# C0330 bad-continuation
# C0415 import-outside-toplevel
# E0401 import-error
# E0611 no-name-in-module
# R0201 no-self-use
# R0801 duplicat-code
# R0901 too-many-ancestors
# R0904 too-many-public-methods
# R0913 too-many-arguments
# R0912 too-many-branches
# R0914 too-many-locals
# R0915 too-many-statements
# R0916 too-many-boolean-expressions
# R1702 too-many-nested-blocks
# R1710 inconsistent-return-statements
# R1732 consider-using-with
# R1725 super-with-arguments
# W0201 attribute-defined-outside-init
# W0221 arguments-differ
# W0223 abstract-method
# W0231 super-init-not-called
# W0233 non-parent-init-called
# W0237 arguments-renamed
# W0603 global-statement
# W0613 unused-argument
# W0707 raise-missing-from
# W1404 implicit-str-concat
# W1406 redundant-u-string-prefix
