import os
import sys
from ftplib import FTP_TLS
from pathlib import Path
import functools
from typing import Any

from rich.console import Console

FTP_URL = 'panoramix.gajim.org'
FTP_USER = os.environ['FTP_USER']
FTP_PASS = os.environ['FTP_PASS']

WINDOWS_NIGHTLY_FOLDER = 'win_snap'

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
    return tag.removesuffix('gajim-')


def get_dir_list(ftp: FTP_TLS) -> list[str]:
    return [x[0] for x in ftp.mlsd()]


def ensure_folder_exists(ftp: FTP_TLS, dirname: str) -> None:
    dir_list = get_dir_list(ftp)
    if dirname not in dir_list:
        ftp.mkd(dirname)


def upload_all_from_dir(ftp: FTP_TLS, dir: Path) -> None:
    for file_path in dir.iterdir():
        console.print('Upload file', file_path.name)
        with open(file_path, 'rb') as f:
            ftp.storbinary('STOR ' + file_path.name, f)


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
    folder = get_release_folder_from_tag(tag)
    ensure_folder_exists(ftp, folder)
    ftp.cwd(folder)
    upload_all_from_dir(ftp, filedir)


@ftp_connection
def deploy_linux_nightly():
    raise NotImplementedError


@ftp_connection
def deploy_linux_release():
    raise NotImplementedError


if __name__ == '__main__':
    filedir = Path(sys.argv[1])
    current_module = sys.modules[__name__]
    method = getattr(current_module, get_deploy_method())
    method(filedir)
