# Copyright (C) 2009 Bruno Tarquini <btarquini AT gmail.com>
#
# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

from typing import Callable
from typing import Optional

import logging
import os
import sys
import time
from datetime import datetime

from gajim.common import app
from gajim.common import configpaths
from gajim.common.i18n import _

LogCallback = Callable[[logging.LogRecord], None]


def parseLogLevel(arg: str) -> int:
    '''
    Either numeric value or level name from logging module
    '''
    if arg.isdigit():
        return int(arg)
    if arg.isupper() and hasattr(logging, arg):
        return getattr(logging, arg)
    print(_('%s is not a valid loglevel') % repr(arg), file=sys.stderr)
    return 0


def parseLogTarget(arg: str) -> str:
    '''
    [gajim.]c.x.y  ->  gajim.c.x.y
    .other_logger  ->  other_logger
    <None>         ->  gajim
    '''
    arg = arg.lower()
    if not arg:
        return 'gajim'
    if arg.startswith('.'):
        return arg[1:]
    if arg.startswith('gajim'):
        return arg
    return 'gajim.' + arg


def parseAndSetLogLevels(arg: str) -> None:
    '''
    [=]LOGLEVEL     ->  gajim=LOGLEVEL
    gajim=LOGLEVEL  ->  gajim=LOGLEVEL
    .other=10       ->  other=10
    .=10            ->  <nothing>
    c.x.y=c.z=20    ->  gajim.c.x.y=20
                        gajim.c.z=20
    gajim=10,c.x=20 ->  gajim=10
                        gajim.c.x=20
    '''
    for directive in arg.split(','):
        directive = directive.strip()
        if not directive:
            continue
        if '=' not in directive:
            directive = '=' + directive
        targets, level = directive.rsplit('=', 1)
        level = parseLogLevel(level.strip())
        for target in targets.split('='):
            target = parseLogTarget(target.strip())
            if target:
                logging.getLogger(target).setLevel(level)
                print('Logger %s level set to %d' % (target, level),
                      file=sys.stderr)


class Colors:
    NONE = chr(27) + '[0m'
    BLACK = chr(27) + '[30m'
    RED = chr(27) + '[31m'
    GREEN = chr(27) + '[32m'
    BROWN = chr(27) + '[33m'
    BLUE = chr(27) + '[34m'
    MAGENTA = chr(27) + '[35m'
    CYAN = chr(27) + '[36m'
    LIGHT_GRAY = chr(27) + '[37m'
    DARK_GRAY = chr(27) + '[30;1m'
    BRIGHT_RED = chr(27) + '[31;1m'
    BRIGHT_GREEN = chr(27) + '[32;1m'
    YELLOW = chr(27) + '[33;1m'
    BRIGHT_BLUE = chr(27) + '[34;1m'
    PURPLE = chr(27) + '[35;1m'
    BRIGHT_CYAN = chr(27) + '[36;1m'
    WHITE = chr(27) + '[37;1m'


def colorize(text: str, color: str) -> str:
    return color + text + Colors.NONE


class CustomStreamHandler(logging.StreamHandler):  # pyright: ignore
    def __init__(self) -> None:
        super().__init__()  # pyright: ignore
        self._callback: LogCallback | None = None

    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)

        if record.levelno >= logging.WARNING:
            app.logging_records.append(record)
            if self._callback is not None:
                self._callback(record)

    def set_callback(self,
                     func: LogCallback | None
                     ) -> None:
        self._callback = func


class FancyFormatter(logging.Formatter):
    '''
    An eye-candy formatter with Colors
    '''
    colors_mapping = {
        'DEBUG': Colors.BLUE,
        'INFO': Colors.GREEN,
        'WARNING': Colors.BROWN,
        'ERROR': Colors.RED,
        'CRITICAL': Colors.BRIGHT_RED,
    }

    def __init__(self,
                 fmt: Optional[str] = None,
                 datefmt: Optional[str] = None,
                 use_color: bool = False) -> None:
        logging.Formatter.__init__(self, fmt, datefmt)
        self.use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        level = record.levelname
        record.levelname = '(%s)' % level[0]

        if self.use_color:
            c = FancyFormatter.colors_mapping.get(level, '')
            record.levelname = colorize(record.levelname, c)
            record.name = '%-25s' % colorize(record.name, Colors.CYAN)
        else:
            record.name = '%-25s|' % record.name

        return logging.Formatter.format(self, record)


def init() -> None:
    '''
    Initialize the logging system
    '''

    if app.get_debug_mode():
        _cleanup_debug_logs()
        _redirect_output()

    use_color = False
    if os.name != 'nt':
        use_color = sys.stderr.isatty()

    _custom_stream_handler.setFormatter(
        FancyFormatter(
            '%(asctime)s %(levelname)s %(name)-35s %(message)s',
            '%x %H:%M:%S',
            use_color
        )
    )

    root_log = logging.getLogger('gajim')
    root_log.setLevel(logging.WARNING)
    root_log.addHandler(_custom_stream_handler)
    root_log.propagate = False

    root_log = logging.getLogger('nbxmpp')
    root_log.setLevel(logging.ERROR)
    root_log.addHandler(_custom_stream_handler)
    root_log.propagate = False

    root_log = logging.getLogger('gnupg')
    root_log.setLevel(logging.WARNING)
    root_log.addHandler(_custom_stream_handler)
    root_log.propagate = False

    root_log = logging.getLogger('omemo_dr')
    root_log.setLevel(logging.WARNING)
    root_log.addHandler(_custom_stream_handler)
    root_log.propagate = False

    # GAJIM_DEBUG is set only on Windows when using Gajim-Debug.exe
    # Gajim-Debug.exe shows a command line prompt and we want to redirect
    # log output to it
    if app.get_debug_mode() or os.environ.get('GAJIM_DEBUG', False):
        set_verbose()


def set_loglevels(loglevels_string: str) -> None:
    parseAndSetLogLevels(loglevels_string)


def set_verbose() -> None:
    parseAndSetLogLevels('gajim=DEBUG')
    parseAndSetLogLevels('.nbxmpp=INFO')
    parseAndSetLogLevels('.omemo_dr=DEBUG')


def set_quiet() -> None:
    parseAndSetLogLevels('gajim=CRITICAL')
    parseAndSetLogLevels('.nbxmpp=CRITICAL')
    parseAndSetLogLevels('.omemo_dr=CRITICAL')


def get_stream_handler() -> CustomStreamHandler:
    return _custom_stream_handler


def _redirect_output() -> None:
    debug_folder = configpaths.get('DEBUG')
    date = datetime.today().strftime('%d%m%Y-%H%M%S')
    filename = '%s-debug.log' % date
    fd = open(debug_folder / filename, 'a', encoding='utf8')
    sys.stderr = sys.stdout = fd


def _cleanup_debug_logs() -> None:
    debug_folder = configpaths.get('DEBUG')
    debug_files = list(debug_folder.glob('*-debug.log*'))
    now = time.time()
    for file in debug_files:
        # Delete everything older than 3 days
        if file.stat().st_ctime < now - 259200:
            file.unlink()


_custom_stream_handler = CustomStreamHandler()


if __name__ == '__main__':
    init()

    set_loglevels('gajim.c=DEBUG,INFO')

    log = logging.getLogger('gajim')
    log.debug('debug')
    log.info('info')
    log.warning('warn')
    log.error('error')
    log.critical('critical')

    log = logging.getLogger('gajim.c.x.dispatcher')
    log.debug('debug')
    log.info('info')
    log.warning('warn')
    log.error('error')
    log.critical('critical')
