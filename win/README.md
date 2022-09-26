# Windows Installer

We use [msys2](https://www.msys2.org/) for creating the Windows installer and development on Windows.

Please note that Windows 7 support has been dropped.

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

### GtkInspector

For Gtk Inspector to work, add the following registry key

```
HKEY_CURRENT_USER\Software\GSettings\org\gtk\settings\debug
DWORD enable-inspector-keybinding = 1
```

Afterwards press CTRL + SHIFT + I, to  activate GtkInspector

## Build Gajim / Create an Installer

Follow the steps in the Development section, but instead of `./dev_env.sh` execute `./build.sh i686` or `./build.sh x86_64`.

Both the installer and the portable installer should appear in `C:\msys64\home\USER\gajim\win\_build_root`.
