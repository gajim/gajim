# Download the file to a specific location
$clnt = new-object System.Net.WebClient
$url = "https://gajim.org/downloads/snap/win/build/site-packages.zip"
$file = "c:\site-packages.zip"
$clnt.DownloadFile($url,$file)

# Unzip the file to specified location
$shell_app=new-object -com shell.application 
$zip_file = $shell_app.namespace($file) 
$destination = $shell_app.namespace("C:\Python34\Lib\site-packages")
$destination.Copyhere($zip_file.items())
