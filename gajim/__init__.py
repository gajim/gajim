import subprocess

__version__ = "0.99.1"

try:
    node = subprocess.Popen('git rev-parse --short=12 HEAD', shell=True,
        stdout=subprocess.PIPE).communicate()[0]
    if node:
        __version__ += '+' + node.decode('utf-8').strip()
except Exception:
    pass

