# Build Gajim on macOS

To build Gajim on macOS, you can follow [the wiki page](https://gitlab.com/gajim/gajim/-/wikis/help/Gajim-on-macOS).

But in this directory we also provide a Bash script (`gajim-macos-helper.sh`) to help build and run Gajim on Mac OS.

## Requirements for this script

You just need [Brew](https://brew.sh) (follow instructions on the website) and Bash (installed by default on macOS), the script will install and do the rest.

## Usage

Execute `gajim-macos-helper.sh build` from the root directory of this repository.

Afterwards run `gajim-macos-helper.sh start` to run Gajim or `gajim-macos-helper.sh build create-dmg` to create the dmg bundle.

You can pass a branch or tag to the `build` command to build a specific version.

```bash
gajim-macos-helper.sh build 2.6.0
```

#### Build in CI mode

Define `GAJIM_CI_BUILD=1` when the script is run in CI, this executes all steps without virtual environment.
