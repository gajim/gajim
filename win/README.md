# Windows Installer

We use [msys2](https://www.msys2.org/) for creating the Windows installer and development on Windows.

## Development

Download [msys2](https://www.msys2.org/) (`msys2-x86_64-xxx.exe`) and follow the install instructions on the [msys2](https://www.msys2.org/) startpage (**Important!**)

* Fork the master branch on dev.gajim.org
* Execute `C:\msys64\msys2_shell.cmd -mingw64`
* Run `pacman -S git` to install git
* Run `git clone https://dev.gajim.org/USERNAME/gajim.git`
* Run `cd gajim/win` to end up where this README exists.
* Execute `./dev_env.sh` to install all the needed dependencies.
* Now go to the git root dir `cd ..`
* Launch Gajim `./launch.py`

### GTK Inspector

For GTK Inspector to work, add the following registry key

```text
HKEY_CURRENT_USER\Software\GSettings\org\gtk\gtk4\settings\debug
DWORD (32 bits) enable-inspector-keybinding = 1
```

Afterwards press CTRL + SHIFT + I to  activate GTK Inspector

## Build Gajim / Create an Installer

Follow the steps in the Development section, but instead of `./dev_env.sh` execute `./build.sh`.

Both the installer and the portable installer should appear in `C:\msys64\home\USER\gajim\win\_build_root`.

## Register Development App from msixbundle

To test Gajim's Microsoft Store msix bundle, the following steps are necessary:

1. Either build the msixbundle locally by running `./build.sh` as described above, or download a nightly build and place it in `C:\msys64\home\USER\gajim\win\_build_root\Gajim.msixbundle`
2. Run `./unpack_msixbundle.sh`, which unpacks the bundle to `C:\msys64\home\USER\gajim\win\_build_root\unpack\Gajim`
3. Open `C:\msys64\home\USER\gajim\win\_build_root\unpack\Gajim` in a PowerShell
4. For easier debugging, change `bin\Gajim.exe` to `bin\Gajim-Debug.exe` in `AppxManifest.xml`, like this: `<Application Id="Gajim" Executable="bin\Gajim-Debug.exe" EntryPoint="Windows.FullTrustApplication">`
5. Now register the app by running `Add-AppxPackage –Register AppxManifest.xml` from a PowerShell
6. Registering the app again requires a version bump in `AppxManifest.xml` (or uninstalling the Gajim app)

To modify code, you can replace `.pyc` files by their equivalent `.py` files from this repo. Gajim's code within the App installation can be found in `C:\msys64\home\USER\gajim\win\_build_root\unpack\Gajim\lib\python3.11\site-packages\gajim`. Code changes do not require to re-register the app.
