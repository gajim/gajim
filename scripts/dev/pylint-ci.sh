#!/bin/sh
PYLINT=${PYLINT:-pylint}

"$PYLINT" --disable=C0103,C0302,C0301,C0330,E0203,E0401,E0611,E0710,E0712,E1101,E1133,E1136,R0201,R0901,R0904,R0912,R0913,R0914,R0915,R0916,R1702,R1710,W0201,W0212,W0221,W0223,W0231,W0233,W0603,W0613 "$@"

# C0103 invalid-name
# C0301 line-too-long
# C0302 too-many-lines
# C0330 bad-continuation
# E0203 access-member-before-definition
# E0401 import-error
# E0611 no-name-in-module
# E0710 raising-non-exception   - GLib.GError is not recognized
# E0712 catching-non-exception  - GLib.GError is not recognized
# E1101 no-member
# E1133 not-an-iterable
# E1136 unsubscriptable-object
# R0201 no-self-use
# R0901 too-many-ancestors
# R0904 too-many-public-methods
# R0913 too-many-arguments
# R0912 too-many-branches
# R0914 too-many-locals
# R0915 too-many-statements
# R0916 too-many-boolean-expressions
# R1702 too-many-nested-blocks
# R1710 inconsistent-return-statements
# W0201 attribute-defined-outside-init
# W0212 protected-access
# W0221 arguments-differ
# W0223 abstract-method
# W0231 super-init-not-called
# W0233 non-parent-init-called
# W0603 global-statement
# W0613 unused-argument
