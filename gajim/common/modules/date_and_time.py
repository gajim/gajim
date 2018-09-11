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

# XEP-0082: XMPP Date and Time Profiles

import re
import time
from datetime import datetime, timedelta, timezone, tzinfo


PATTERN_DATETIME = re.compile(
    r'([0-9]{4}-[0-9]{2}-[0-9]{2})'
    r'T'
    r'([0-9]{2}:[0-9]{2}:[0-9]{2})'
    r'(\.[0-9]{0,6})?'
    r'(?:[0-9]+)?'
    r'(?:(Z)|(?:([-+][0-9]{2}):([0-9]{2})))$'
)

PATTERN_DELAY = re.compile(
    r'([0-9]{4}-[0-9]{2}-[0-9]{2})'
    r'T'
    r'([0-9]{2}:[0-9]{2}:[0-9]{2})'
    r'(\.[0-9]{0,6})?'
    r'(?:[0-9]+)?'
    r'(?:(Z)|(?:([-+][0]{2}):([0]{2})))$'
)


ZERO = timedelta(0)
HOUR = timedelta(hours=1)
SECOND = timedelta(seconds=1)

STDOFFSET = timedelta(seconds=-time.timezone)
if time.daylight:
    DSTOFFSET = timedelta(seconds=-time.altzone)
else:
    DSTOFFSET = STDOFFSET

DSTDIFF = DSTOFFSET - STDOFFSET


class LocalTimezone(tzinfo):
    '''
    A class capturing the platform's idea of local time.
    May result in wrong values on historical times in
    timezones where UTC offset and/or the DST rules had
    changed in the past.
    '''
    def fromutc(self, dt):
        assert dt.tzinfo is self
        stamp = (dt - datetime(1970, 1, 1, tzinfo=self)) // SECOND
        args = time.localtime(stamp)[:6]
        dst_diff = DSTDIFF // SECOND
        # Detect fold
        fold = (args == time.localtime(stamp - dst_diff))
        return datetime(*args, microsecond=dt.microsecond,
                        tzinfo=self, fold=fold)

    def utcoffset(self, dt):
        if self._isdst(dt):
            return DSTOFFSET
        return STDOFFSET

    def dst(self, dt):
        if self._isdst(dt):
            return DSTDIFF
        return ZERO

    def tzname(self, dt):
        return 'local'

    @staticmethod
    def _isdst(dt):
        tt = (dt.year, dt.month, dt.day,
              dt.hour, dt.minute, dt.second,
              dt.weekday(), 0, 0)
        stamp = time.mktime(tt)
        tt = time.localtime(stamp)
        return tt.tm_isdst > 0


def parse_datetime(timestring, check_utc=False,
                   convert='utc', epoch=False):
    '''
    Parse a XEP-0082 DateTime Profile String

    :param timestring: a XEP-0082 DateTime profile formated string

    :param check_utc:  if True, returns None if timestring is not
                       a timestring expressing UTC

    :param convert:    convert the given timestring to utc or local time

    :param epoch:      if True, returns the time in epoch

    Examples:
    '2017-11-05T01:41:20Z'
    '2017-11-05T01:41:20.123Z'
    '2017-11-05T01:41:20.123+05:00'

    return a datetime or epoch
    '''
    if convert not in (None, 'utc', 'local'):
        raise TypeError('"%s" is not a valid value for convert')
    if check_utc:
        match = PATTERN_DELAY.match(timestring)
    else:
        match = PATTERN_DATETIME.match(timestring)

    if match:
        timestring = ''.join(match.groups(''))
        strformat = '%Y-%m-%d%H:%M:%S%z'
        if match.group(3):
            # Fractional second addendum to Time
            strformat = '%Y-%m-%d%H:%M:%S.%f%z'
        if match.group(4):
            # UTC string denoted by addition of the character 'Z'
            timestring = timestring[:-1] + '+0000'
        try:
            date_time = datetime.strptime(timestring, strformat)
        except ValueError:
            pass
        else:
            if not check_utc and convert == 'utc':
                date_time = date_time.astimezone(timezone.utc)
            if convert == 'local':
                date_time = date_time.astimezone(LocalTimezone())
            if epoch:
                return date_time.timestamp()
            return date_time
    return None
