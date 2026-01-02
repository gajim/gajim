# Build Gajim on MacOS

To build omemo-dr, nbxmpp and Gajim on MacOS, you can follow [the wiki page](https://dev.gajim.org/gajim/gajim/-/wikis/help/Gajim-on-macOS).

But in this directory we also provide a Bash script (`gajim-macos-helper.sh`) to help creating virtual environments for omemo-dr, nbxmpp and Gajim in Mac OS, build it, start it from the virtual environment, and also create a `.dmg` bundle.

## Requirements for this script

You just need [Brew](https://brew.sh) (follow instructions on the website) and Bash (installed by default on MacOS), the script will install and do the rest.

## Usage

The `gajim-macos-helper.sh` script need to be copied alone in an empty directory of your choice, without anything else.

Always run the `gajim-macos-helper.sh` script from within the directory where you placed it (`./gajim-macos-helper.sh <argument>` style).

### Build specific version of omemo-dr, nbxmpp and Gajim

Always check the versions variables inside the `gajim-macos-helper.sh` script: check tags dates on Gitlab to make [omemo-dr](https://dev.gajim.org/gajim/omemo-dr/-/tags), [nbxmpp](https://dev.gajim.org/gajim/python-nbxmpp/-/tags) and [Gajim](https://dev.gajim.org/gajim/gajim/-/tags) versions match (example: Gajim version `2.4.1` match omemo-dr version `1.1.0` and nbxmpp version `7.0.0`)

To build (or rebuild) a new version of omemo-dr, nbxmpp and Gajim, run:

```
./gajim-macos-helper.sh build
```

> Note: If a previous build was done this way, it will be destroyed first. This command install dependencies via Brew, create a Python virtual environment and build omemo-dr, nbxmpp and Gajim.

#### Build in CI mode

The "CI mode" install all dependencies system side (without any virtual environment) and is used with the goal of building a `.dmg` file after this. It is used mostly in CI or containers, don't use it for dev purpose.

```
./gajim-macos-helper.sh build ci
```

### Start the Gajim version you just built

To start built version, run:

```
./gajim-macos-helper.sh start
```

> Note: This command enter inside the Python virtual environment and launch Gajim.

### Create a DMG file (CI mode)

The "CI mode" install all dependencies system side (without any virtual environment) and need to be run after the `build ci` command. It is used mostly in CI or containers, don't use it for dev purpose.

To create a `.dmg` file, run:

```
./gajim-macos-helper.sh create-dmg ci
```

> Note: This command use PyInstaller to create a `gajim-<version>.dmg` file.
