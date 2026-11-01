# Windows Installer

We use [msys2](https://www.msys2.org/) for creating the Windows installer and development on Windows.

## Development

Download [msys2](https://www.msys2.org/) (`msys2-x86_64-xxx.exe`) and follow the install instructions on the [msys2](https://www.msys2.org/) startpage (**Important!**)

* Fork the master branch on gitlab.com
* Start a UCRT64 shell
* Run `pacman -Syu` to update the runtime
* Run `pacman -S git` to install git
* Run `git clone https://gitlab.com/USERNAME/gajim.git`
* Run `cd gajim`
* Run `./platform/win/build.sh setup
* Launch Gajim `gajim`

### GTK Inspector

For GTK Inspector to work, add the following registry key

```text
HKEY_CURRENT_USER\Software\GSettings\org\gtk\gtk4\settings\debug
DWORD (32 bits) enable-inspector-keybinding = 1
```

Afterwards press CTRL + SHIFT + I to  activate GTK Inspector

## Build Gajim / Create an Installer

Run `./platform/win/build.sh build-installer`

All installers should appear in `dist/win`.

## Register Development App from msixbundle

To test Gajim's Microsoft Store msix bundle, the following steps are necessary:

1. Run `./platform/win/build.sh msix-unpack FILE DEST`, which unpacks the bundle to `DEST`
2. Open PowerShell and go to `DEST/unpack`
3. Now register the app by running `Add-AppxPackage –Register AppxManifest.xml` from PowerShell
5. Registering the app again requires a version bump in `AppxManifest.xml` (or uninstalling the Gajim app)

To modify code, you can replace `.pyc` files by their equivalent `.py` files from this repo. Gajim's code within the App installation can be found in `DEST\unpack\Gajim\_internal\python3.XX\site-packages\gajim`. Code changes do not require to re-register the app.
