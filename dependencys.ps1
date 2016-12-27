# Download Dependencys

$clnt = new-object System.Net.WebClient
$url = "https://gajim.org/downloads/snap/win/build/pycairo-1.8.10.win32-py2.7.msi"
$file = "c:\cairo.msi"
$clnt.DownloadFile($url,$file)

$url = "https://gajim.org/downloads/snap/win/build/pygobject-2.28.3.win32-py2.7.msi"
$file = "c:\pygobject.msi"
$clnt.DownloadFile($url,$file)

$url = "https://gajim.org/downloads/snap/win/build/pygtk-2.24.0.win32-py2.7.msi"
$file = "c:\pygtk.msi"
$clnt.DownloadFile($url,$file)

$url = "https://gajim.org/downloads/snap/win/build/pygoocanvas-0.14.2.win32-py2.7.msi"
$file = "c:\pygoocanvas.msi"
$clnt.DownloadFile($url,$file)

$url = "https://gajim.org/downloads/snap/win/build/Bonjour64.msi"
$file = "c:\bonjour.msi"
$clnt.DownloadFile($url,$file)