*Release date: xx xxx xxxx*

## Preparations

* [ ] Raise nbxmpp version (if necessary)

## Build

* [ ] Merge translations from Weblate
* [ ] Update IANA data with `./scripts/get_iana_data.py gajim/common/iana.py`
* [ ] Run `./scripts/update_flatpak_manifest.py`
* [ ] Run `./scripts/bump_version.py x.x.x`
* [ ] Push release tag `x.x.x`
* [ ] Upload .msixbundle to Windows store
* [ ] Close release milestone after new milestone has been created automatically

## Update

* [ ] Website: Write announcement post with changelog
* [ ] Website: Update screenshots
* [ ] Website: Merge website translations from Weblate
* [ ] MUC: Update MUC subject on gajim@conference.gajim.org
* [ ] Publish release post on [Fosstodon](https://fosstodon.org/@gajim)
