# Download the file to a specific location
$clnt = new-object System.Net.WebClient
$url = "http://www.funkroom.net/files/site-packages.zip"
$file = "c:\site-packages.zip"
$clnt.DownloadFile($url,$file)

# Unzip the file to specified location
$shell_app=new-object -com shell.application 
$zip_file = $shell_app.namespace($file) 
$destination = $shell_app.namespace("C:\Python34\Lib\site-packages")
$destination.Copyhere($zip_file.items())

# Download gettext
$url = "https://github.com/mlocati/gettext-iconv-windows/releases/download/v0.19.8.1-v1.14/gettext0.19.8.1-iconv1.14-static-32.zip"
$file = "c:\gettext0.19.8.1-iconv1.14-static-32.zip"
$clnt.DownloadFile($url,$file)

# Unzip the file to specified location
$shell_app=new-object -com shell.application 
$zip_file = $shell_app.namespace($file)
New-Item -ItemType directory -Path C:\gettext
$destination = $shell_app.namespace("C:\gettext")
$destination.Copyhere($zip_file.items())
