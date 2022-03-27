from typing import Any
from typing import Optional

import functools
import os
import sys
from datetime import date
from ftplib import FTP_TLS
from pathlib import Path

from rich.console import Console


FTP_URL = 'panoramix.gajim.org'
FTP_USER = os.environ['FTP_USER']
FTP_PASS = os.environ['FTP_PASS']

WINDOWS_NIGHTLY_FOLDER = 'downloads/snap/win'
LINUX_NIGHTLY_FOLDER = 'downloads/snap'

RELEASE_FOLDER_BASE = 'downloads'

console = Console()


def ftp_connection(func: Any) -> Any:
    @functools.wraps(func)
    def func_wrapper(filedir: Path) -> None:
        ftp = FTP_TLS(FTP_URL, FTP_USER, FTP_PASS)
        console.print('Successfully connected to', FTP_URL)
        func(ftp, filedir)
        ftp.quit()
        console.print('Quit')
        return
    return func_wrapper


def get_release_folder_from_tag(tag: str) -> str:
    numbers = tag.split('.')
    return '.'.join(numbers[:2])


def get_gajim_tag() -> str:
    tag = os.environ.get('CI_COMMIT_TAG')
    if tag is None:
        exit('No tag found')
    return tag.removeprefix('gajim-')


def find_linux_tarball(filedir: Path) -> Path:
    files = list(filedir.glob('gajim-*.tar.gz'))
    if len(files) != 1:
        exit('Unknown files found')
    return files[0]


def get_dir_list(ftp: FTP_TLS) -> list[str]:
    return [x[0] for x in ftp.mlsd()]


def create_release_folder(ftp: FTP_TLS, tag: str) -> None:
    ftp.cwd(RELEASE_FOLDER_BASE)
    folder = get_release_folder_from_tag(tag)
    dir_list = get_dir_list(ftp)
    if folder not in dir_list:
        ftp.mkd(folder)
    ftp.cwd(folder)


def upload_all_from_dir(ftp: FTP_TLS, filedir: Path) -> None:
    for filepath in filedir.iterdir():
        upload_file(ftp, filepath)


def upload_file(ftp: FTP_TLS,
                filepath: Path,
                name: Optional[str] = None) -> None:

    if name is None:
        name = filepath.name

    console.print('Upload file', filepath.name, 'as', name)
    with open(filepath, 'rb') as f:
        ftp.storbinary('STOR ' + name, f)


def get_deploy_method() -> str:
    deploy_type = os.environ['DEPLOY_TYPE']
    is_nightly = bool(os.environ.get('GAJIM_NIGHTLY_BUILD'))
    if is_nightly:
        return f'deploy_{deploy_type}_nightly'
    return f'deploy_{deploy_type}_release'


@ftp_connection
def deploy_windows_nightly(ftp: FTP_TLS, filedir: Path) -> None:
    ftp.cwd(WINDOWS_NIGHTLY_FOLDER)
    upload_all_from_dir(ftp, filedir)


@ftp_connection
def deploy_windows_release(ftp: FTP_TLS, filedir: Path) -> None:
    tag = get_gajim_tag()
    create_release_folder(ftp, tag)
    upload_all_from_dir(ftp, filedir)


@ftp_connection
def deploy_linux_nightly(ftp: FTP_TLS, filedir: Path) -> None:
    ftp.cwd(LINUX_NIGHTLY_FOLDER)
    filepath = find_linux_tarball(filedir)
    filename = f'gajim-{date.today().isoformat()}.tar.gz'
    upload_file(ftp, filepath, name=filename)


@ftp_connection
def deploy_linux_release(ftp: FTP_TLS, file: Path) -> None:
    tag = get_gajim_tag()
    create_release_folder(ftp, tag)
    filepath = find_linux_tarball(filedir)
    filename = f'gajim-{tag}.tar.gz'
    upload_file(ftp, filepath, name=filename)


if __name__ == '__main__':
    filedir = Path(sys.argv[1])
    current_module = sys.modules[__name__]
    method = getattr(current_module, get_deploy_method())
    method(filedir)
