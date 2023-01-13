
import unittest
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from gajim.common import app
from gajim.common.helpers import get_uf_relative_time
from gajim.common.settings import Settings

app.settings = Settings(in_memory=True)


class GetRelativeTimeTest(unittest.TestCase):
    '''Tests for the get_uf_relative_time function.'''

    def test_sub_1_minute(self):
        '''Test timedelta less than 1 minute'''
        timenow = datetime(2023, 1, 2, 3, 4, 0, tzinfo=timezone.utc)
        timestamp1 = timenow - timedelta(seconds=30)
        self.assertEqual(get_uf_relative_time(timestamp1.timestamp(),
                                              timenow.timestamp()), 'Just now')

    def test_sub_15_minutes(self):
        '''Test timedelta less than 15 minutes and more than 1 minute ago'''
        timenow = datetime(2023, 1, 2, 3, 4, 0, tzinfo=timezone.utc)
        timestamp1 = timenow - timedelta(minutes=3)
        self.assertEqual(get_uf_relative_time(timestamp1.timestamp(),
                                              timenow.timestamp()),
                         '3 mins ago')

    def test_sub_15_minutes_next_day(self):
        '''Test timedelta less than 15 minutes and it is the next day'''
        timenow = datetime(2023, 1, 1, 0, 5, 0, tzinfo=timezone.utc)
        timestamp1 = timenow - timedelta(minutes=10)
        self.assertEqual(get_uf_relative_time(timestamp1.timestamp(),
                                              timenow.timestamp()),
                         '10 mins ago')

    def test_today(self):
        '''Test today: same day and more than 15 minutes ago'''
        timenow = datetime(2023, 1, 2, 12, 0, 0, tzinfo=timezone.utc)
        timestamp1 = timenow - timedelta(hours=4)
        self.assertEqual(get_uf_relative_time(timestamp1.timestamp(),
                                              timenow.timestamp()),
                         timestamp1.strftime(app.settings.get('time_format')))

    def test_yesterday_less_than_24h(self):
        '''Test yesterday and less than 24h ago'''
        timenow = datetime(2023, 1, 2, 12, 0, 0, tzinfo=timezone.utc)
        timestamp1 = datetime(2023, 1, 1, 14, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(get_uf_relative_time(timestamp1.timestamp(),
                                              timenow.timestamp()), 'Yesterday')

    def test_yesterday_more_than_24h(self):
        '''Test yesterday and more than 24h ago'''
        timenow = datetime(2023, 1, 2, 12, 0, 0, tzinfo=timezone.utc)
        timestamp1 = datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(get_uf_relative_time(timestamp1.timestamp(),
                                              timenow.timestamp()),
                         'Yesterday')

    def test_weekday(self):
        '''Test weekday: timestamp older than yesterday and less
        than 7 days ago, should return the weekday, i.e. 'Sun' for Sunday'''
        timenow = datetime(2023, 1, 5, 1, 2, 3, tzinfo=timezone.utc)
        timestamp1 = datetime(2023, 1, 1, 4, 5, 6, tzinfo=timezone.utc)
        self.assertEqual(get_uf_relative_time(timestamp1.timestamp(),
                                              timenow.timestamp()),
                         timestamp1.strftime('%a'))

    def test_month_day(self):
        '''Test month_day: timestamp more than 7 days ago but less than 365'''
        timenow = datetime(2023, 1, 5, 1, 2, 3, tzinfo=timezone.utc)
        timestamp1 = datetime(2022, 11, 15, 4, 5, 6, tzinfo=timezone.utc)
        self.assertEqual(get_uf_relative_time(timestamp1.timestamp(),
                                              timenow.timestamp()),
                         timestamp1.strftime('%b %d'))

    def test_year(self):
        '''Test year: timestamp more than 365 days ago'''
        timenow = datetime(2023, 1, 5, 1, 2, 3, tzinfo=timezone.utc)
        timestamp1 = datetime(2022, 1, 1, 4, 5, 6, tzinfo=timezone.utc)
        self.assertEqual(get_uf_relative_time(timestamp1.timestamp(),
                                              timenow.timestamp()), '2022')


if __name__ == '__main__':
    unittest.main()
