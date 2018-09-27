SCRIPTDIR=$(dirname $0)

mypy gajim
${SCRIPTDIR}/pylint-ci.sh --jobs=0 gajim
