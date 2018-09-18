mypy -p gajim.common.modules --follow-imports=skip
pylint --jobs=2 --disable=C0103,C0302,C0330,C0411,C0412,C0413,E0203,E0401,E0611,E0710,E0712,E1101,E1102,E1128,E1133,E1136,R0201,R0901,R0904,R0913,R0916,R1702,R1706,R1711,R1716,W0143,W0201,W0212,W0221,W0223,W0311,W0401,W0603,W0613,W0614 gajim

# C0103 invalid-name
# C0302 too-many-lines
# C0330 bad-continuation
# C0411 wrong-import-order
# C0412 ungrouped-imports
# C0413 wrong-import-position
# E0203 access-member-before-definition
# E0401 import-error
# E0611 no-name-in-module
# E0710 raising-non-exception   - GLib.GError is not recognized
# E0712 catching-non-exception  - GLib.GError is not recognized
# R0201 no-self-use
# W0143 comparison-with-callable - Dont add to Server CI, only available on pylint 2.0+