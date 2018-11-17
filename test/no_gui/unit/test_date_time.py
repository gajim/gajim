import unittest
from datetime import datetime
from datetime import timezone
from datetime import timedelta

from gajim.common.modules.date_and_time import parse_datetime
from gajim.common.modules.date_and_time import LocalTimezone
from gajim.common.modules.date_and_time import create_tzinfo


class TestDateTime(unittest.TestCase):

    def test_convert_to_utc(self):

        strings = {
            # Valid UTC strings and fractions
            '2017-11-05T01:41:20Z': 1509846080.0,
            '2017-11-05T01:41:20.123Z': 1509846080.123,
            '2017-11-05T01:41:20.123123123+00:00': 1509846080.123123,
            '2017-11-05T01:41:20.123123123123123-00:00': 1509846080.123123,

            # Invalid strings
            '2017-11-05T01:41:20Z+05:00': None,
            '2017-11-05T01:41:20+0000': None,
            '2017-11-05T01:41:20-0000': None,

            # Valid strings with offset
            '2017-11-05T01:41:20-05:00': 1509864080.0,
            '2017-11-05T01:41:20+05:00': 1509828080.0,
        }

        strings2 = {
            # Valid strings with offset
            '2017-11-05T01:41:20-05:00': datetime(2017, 11, 5, 1, 41, 20, 0, create_tzinfo(hours=-5)),
            '2017-11-05T01:41:20+05:00': datetime(2017, 11, 5, 1, 41, 20, 0, create_tzinfo(hours=5)),
        }

        for time_string, expected_value in strings.items():
            result = parse_datetime(time_string, convert='utc', epoch=True)
            self.assertEqual(result, expected_value)

        for time_string, expected_value in strings2.items():
            result = parse_datetime(time_string, convert='utc')
            self.assertEqual(result, expected_value.astimezone(timezone.utc))

    def test_convert_to_local(self):

        strings = {
            # Valid UTC strings and fractions
            '2017-11-05T01:41:20Z': datetime(2017, 11, 5, 1, 41, 20, 0, timezone.utc),
            '2017-11-05T01:41:20.123Z': datetime(2017, 11, 5, 1, 41, 20, 123000, timezone.utc),
            '2017-11-05T01:41:20.123123123+00:00': datetime(2017, 11, 5, 1, 41, 20, 123123, timezone.utc),
            '2017-11-05T01:41:20.123123123123123-00:00': datetime(2017, 11, 5, 1, 41, 20, 123123, timezone.utc),

            # Valid strings with offset
            '2017-11-05T01:41:20-05:00': datetime(2017, 11, 5, 1, 41, 20, 0, create_tzinfo(hours=-5)),
            '2017-11-05T01:41:20+05:00': datetime(2017, 11, 5, 1, 41, 20, 0, create_tzinfo(hours=5)),
        }

        for time_string, expected_value in strings.items():
            result = parse_datetime(time_string, convert='local')
            self.assertEqual(result, expected_value.astimezone(LocalTimezone()))

    def test_no_convert(self):

        strings = {
            # Valid UTC strings and fractions
            '2017-11-05T01:41:20Z': timedelta(0),
            '2017-11-05T01:41:20.123Z': timedelta(0),
            '2017-11-05T01:41:20.123123123+00:00': timedelta(0),
            '2017-11-05T01:41:20.123123123123123-00:00': timedelta(0),

            # Valid strings with offset
            '2017-11-05T01:41:20-05:00': timedelta(hours=-5),
            '2017-11-05T01:41:20+05:00': timedelta(hours=5),
        }

        for time_string, expected_value in strings.items():
            result = parse_datetime(time_string, convert=None)
            self.assertEqual(result.utcoffset(), expected_value)

    def test_check_utc(self):

        strings = {
            # Valid UTC strings and fractions
            '2017-11-05T01:41:20Z': 1509846080.0,
            '2017-11-05T01:41:20.123Z': 1509846080.123,
            '2017-11-05T01:41:20.123123123+00:00': 1509846080.123123,
            '2017-11-05T01:41:20.123123123123123-00:00': 1509846080.123123,

            # Valid strings with offset
            '2017-11-05T01:41:20-05:00': None,
            '2017-11-05T01:41:20+05:00': None,
        }

        for time_string, expected_value in strings.items():
            result = parse_datetime(
                time_string, check_utc=True, epoch=True)
            self.assertEqual(result, expected_value)
