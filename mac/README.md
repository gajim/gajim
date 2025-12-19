# Build Gajim on MacOS

To build nbxmpp and Gajim on MacOS, you can follow [the wiki page](https://dev.gajim.org/gajim/gajim/-/wikis/help/Gajim-on-macOS).

But in this directory we also provide a Bash script (`gajim-macos-helper.sh`) to help creating virtual environments for nbxmpp and Gajim in Mac OS, build it, start it from the virtual environement, and also create a `.dmg` bundle.

## Requirements for this script

You just need [Brew](https://brew.sh) (follow instructions on the website) and Bash (installed by default on MacOS), the script will install and do the rest.

## Usage

The `gajim-macos-helper.sh` script need to be copied alone in an empty directory of your choice, without anything else.

Always run the `gajim-macos-helper.sh` script from within the directory where you placed it (`./gajim-macos-helper.sh <argument>` style).

### Build specific version of nbxmpp and Gajim

Always check the versions variables inside the `gajim-macos-helper.sh` script: check tags dates on Gitlab to make [nbxmpp](https://dev.gajim.org/gajim/python-nbxmpp/-/tags) and [Gajim](https://dev.gajim.org/gajim/gajim/-/tags) versions match (example: Gajim version `2.4.1` match nbxmpp version `7.0.0`)

To build (or rebuild) a new version of nbxmpp and Gajim, run:

```
./gajim-macos-helper.sh build
```

> Note: If a previous build was done this way, it will be destroyed first. This command install dependencies via Brew, create a Python virtual environment and build nbxmpp and Gajim.

### Start the Gajim version you just built

To start built version, run:

```
./gajim-macos-helper.sh start
```

> Note: This command enter inside the Python virtual environment and launch Gajim.

### Create a DMG file (experimental)

To create a `.dmg` file, run:

```
./gajim-macos-helper.sh create-dmg
```

> Note: This command use PyInstaller to create a `gajim-<version>.dmg` file.

> Warning: At this time, the produced `.dmg` file is still not working properly. Some dependencies are missing.
