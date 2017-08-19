# Windows Installer

We use [msys2](http://www.msys2.org/) for creating the Windows installer
and development on Windows.


### Development
-----------

Download [msys2](http://www.msys2.org/) (msys2-x86_64-xxx.exe) and follow the install instructions on the [msys2](http://www.msys2.org/) startpage (**Important!**)

* Fork the master branch on dev.gajim.org
* Execute ``C:\msys64\mingw32.exe``
* Run ``pacman -S git`` to install git
* Run ``git clone https://dev.gajim.org/USERNAME/gajim.git``
* Run ``cd gajim/win`` to end up where this README exists.
* Execute ``./dev_env.sh`` to install all the needed dependencies.
* Now go to the git root dir ``cd ..``
* Launch Gajim ``./launch.py``


### Build Gajim / Creating an Installer
---------------------

Follow the steps in the Development section, but instead of ``./dev_env.sh`` execute ``./build.sh``.

You can supply a git tag ``./build.sh [git-tag]``.

Or dont supply it, then current HEAD is build.

Both the installer and the portable installer should appear in ``C:\msys64\home\USER\gajim\win\_build_root``.

