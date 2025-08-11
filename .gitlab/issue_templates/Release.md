*Release date: xx xxx xxxx*

## Preparations

* [ ] Release new nbxmpp version and raise version in Gajim (if necessary) ([example](https://dev.gajim.org/gajim/gajim/-/commit/92afd65618923085d3392dcb5fb877b9bc71475e))

## Build

* [ ] Merge translations from Weblate
* [ ] Update IANA data with `./scripts/get_iana_data.py gajim/common/iana.py`
* [ ] Run `./scripts/update_flatpak_manifest.py` for `flatpak/org.gajim.Gajim.yaml` and `flatpak/org.gajim.Gajim.Devel.yaml`
* [ ] Run `./scripts/bump_version.py x.x.x` (fetch tags from upstream first)
* [ ] Push release tag `x.x.x`
* [ ] Upload .msixbundle to Windows store
* [ ] Close release milestone after new milestone has been created automatically

## Update

* [ ] Website: Write announcement post with changelog
* [ ] Website: Update screenshots
* [ ] Website: Merge website translations from Weblate
* [ ] MUC: Update MUC subject on gajim@conference.gajim.org
* [ ] Publish release post on [Fosstodon](https://fosstodon.org/@gajim)
