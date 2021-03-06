import nose
import os

import pytz
import numpy as np
import pandas as pd
from pandas import (merge_asof, read_csv,
                    to_datetime, Timedelta)
from pandas.tools.merge import MergeError
from pandas.util import testing as tm
from pandas.util.testing import assert_frame_equal


class TestAsOfMerge(tm.TestCase):
    _multiprocess_can_split_ = True

    def read_data(self, name, dedupe=False):
        path = os.path.join(tm.get_data_path(), name)
        x = read_csv(path)
        if dedupe:
            x = (x.drop_duplicates(['time', 'ticker'], keep='last')
                  .reset_index(drop=True)
                 )
        x.time = to_datetime(x.time)
        return x

    def setUp(self):

        self.trades = self.read_data('trades.csv')
        self.quotes = self.read_data('quotes.csv', dedupe=True)
        self.asof = self.read_data('asof.csv')
        self.tolerance = self.read_data('tolerance.csv')
        self.allow_exact_matches = self.read_data('allow_exact_matches.csv')
        self.allow_exact_matches_and_tolerance = self.read_data(
            'allow_exact_matches_and_tolerance.csv')

    def test_examples1(self):
        """ doc-string examples """

        left = pd.DataFrame({'a': [1, 5, 10],
                             'left_val': ['a', 'b', 'c']})
        right = pd.DataFrame({'a': [1, 2, 3, 6, 7],
                              'right_val': [1, 2, 3, 6, 7]})

        pd.merge_asof(left, right, on='a')

    def test_examples2(self):
        """ doc-string examples """

        trades = pd.DataFrame({
            'time': pd.to_datetime(['20160525 13:30:00.023',
                                    '20160525 13:30:00.038',
                                    '20160525 13:30:00.048',
                                    '20160525 13:30:00.048',
                                    '20160525 13:30:00.048']),
            'ticker': ['MSFT', 'MSFT',
                       'GOOG', 'GOOG', 'AAPL'],
            'price': [51.95, 51.95,
                      720.77, 720.92, 98.00],
            'quantity': [75, 155,
                         100, 100, 100]},
            columns=['time', 'ticker', 'price', 'quantity'])

        quotes = pd.DataFrame({
            'time': pd.to_datetime(['20160525 13:30:00.023',
                                    '20160525 13:30:00.023',
                                    '20160525 13:30:00.030',
                                    '20160525 13:30:00.041',
                                    '20160525 13:30:00.048',
                                    '20160525 13:30:00.049',
                                    '20160525 13:30:00.072',
                                    '20160525 13:30:00.075']),
            'ticker': ['GOOG', 'MSFT', 'MSFT',
                       'MSFT', 'GOOG', 'AAPL', 'GOOG',
                       'MSFT'],
            'bid': [720.50, 51.95, 51.97, 51.99,
                    720.50, 97.99, 720.50, 52.01],
            'ask': [720.93, 51.96, 51.98, 52.00,
                    720.93, 98.01, 720.88, 52.03]},
            columns=['time', 'ticker', 'bid', 'ask'])

        pd.merge_asof(trades, quotes,
                      on='time',
                      by='ticker')

        pd.merge_asof(trades, quotes,
                      on='time',
                      by='ticker',
                      tolerance=pd.Timedelta('2ms'))

        pd.merge_asof(trades, quotes,
                      on='time',
                      by='ticker',
                      tolerance=pd.Timedelta('10ms'),
                      allow_exact_matches=False)

    def test_basic(self):

        expected = self.asof
        trades = self.trades
        quotes = self.quotes

        result = merge_asof(trades, quotes,
                            on='time',
                            by='ticker')
        assert_frame_equal(result, expected)

    def test_basic_categorical(self):

        expected = self.asof
        trades = self.trades.copy()
        trades.ticker = trades.ticker.astype('category')
        quotes = self.quotes.copy()
        quotes.ticker = quotes.ticker.astype('category')

        result = merge_asof(trades, quotes,
                            on='time',
                            by='ticker')
        assert_frame_equal(result, expected)

    def test_basic_left_index(self):

        # GH14253
        expected = self.asof
        trades = self.trades.set_index('time')
        quotes = self.quotes

        result = merge_asof(trades, quotes,
                            left_index=True,
                            right_on='time',
                            by='ticker')
        # left-only index uses right's index, oddly
        expected.index = result.index
        # time column appears after left's columns
        expected = expected[result.columns]
        assert_frame_equal(result, expected)

    def test_basic_right_index(self):

        expected = self.asof
        trades = self.trades
        quotes = self.quotes.set_index('time')

        result = merge_asof(trades, quotes,
                            left_on='time',
                            right_index=True,
                            by='ticker')
        assert_frame_equal(result, expected)

    def test_basic_left_index_right_index(self):

        expected = self.asof.set_index('time')
        trades = self.trades.set_index('time')
        quotes = self.quotes.set_index('time')

        result = merge_asof(trades, quotes,
                            left_index=True,
                            right_index=True,
                            by='ticker')
        assert_frame_equal(result, expected)

    def test_multi_index(self):

        # MultiIndex is prohibited
        trades = self.trades.set_index(['time', 'price'])
        quotes = self.quotes.set_index('time')
        with self.assertRaises(MergeError):
            merge_asof(trades, quotes,
                       left_index=True,
                       right_index=True)

        trades = self.trades.set_index('time')
        quotes = self.quotes.set_index(['time', 'bid'])
        with self.assertRaises(MergeError):
            merge_asof(trades, quotes,
                       left_index=True,
                       right_index=True)

    def test_on_and_index(self):

        # 'on' parameter and index together is prohibited
        trades = self.trades.set_index('time')
        quotes = self.quotes.set_index('time')
        with self.assertRaises(MergeError):
            merge_asof(trades, quotes,
                       left_on='price',
                       left_index=True,
                       right_index=True)

        trades = self.trades.set_index('time')
        quotes = self.quotes.set_index('time')
        with self.assertRaises(MergeError):
            merge_asof(trades, quotes,
                       right_on='bid',
                       left_index=True,
                       right_index=True)

    def test_basic_left_by_right_by(self):

        # GH14253
        expected = self.asof
        trades = self.trades
        quotes = self.quotes

        result = merge_asof(trades, quotes,
                            on='time',
                            left_by='ticker',
                            right_by='ticker')
        assert_frame_equal(result, expected)

    def test_missing_right_by(self):

        expected = self.asof
        trades = self.trades
        quotes = self.quotes

        q = quotes[quotes.ticker != 'MSFT']
        result = merge_asof(trades, q,
                            on='time',
                            by='ticker')
        expected.loc[expected.ticker == 'MSFT', ['bid', 'ask']] = np.nan
        assert_frame_equal(result, expected)

    def test_basic2(self):

        expected = self.read_data('asof2.csv')
        trades = self.read_data('trades2.csv')
        quotes = self.read_data('quotes2.csv', dedupe=True)

        result = merge_asof(trades, quotes,
                            on='time',
                            by='ticker')
        assert_frame_equal(result, expected)

    def test_basic_no_by(self):
        f = lambda x: x[x.ticker == 'MSFT'].drop('ticker', axis=1) \
            .reset_index(drop=True)

        # just use a single ticker
        expected = f(self.asof)
        trades = f(self.trades)
        quotes = f(self.quotes)

        result = merge_asof(trades, quotes,
                            on='time')
        assert_frame_equal(result, expected)

    def test_valid_join_keys(self):

        trades = self.trades
        quotes = self.quotes

        with self.assertRaises(MergeError):
            merge_asof(trades, quotes,
                       left_on='time',
                       right_on='bid',
                       by='ticker')

        with self.assertRaises(MergeError):
            merge_asof(trades, quotes,
                       on=['time', 'ticker'],
                       by='ticker')

        with self.assertRaises(MergeError):
            merge_asof(trades, quotes,
                       by='ticker')

    def test_with_duplicates(self):

        q = pd.concat([self.quotes, self.quotes]).sort_values(
            ['time', 'ticker']).reset_index(drop=True)
        result = merge_asof(self.trades, q,
                            on='time',
                            by='ticker')
        expected = self.read_data('asof.csv')
        assert_frame_equal(result, expected)

    def test_with_duplicates_no_on(self):

        df1 = pd.DataFrame({'key': [1, 1, 3],
                            'left_val': [1, 2, 3]})
        df2 = pd.DataFrame({'key': [1, 2, 2],
                            'right_val': [1, 2, 3]})
        result = merge_asof(df1, df2, on='key')
        expected = pd.DataFrame({'key': [1, 1, 3],
                                 'left_val': [1, 2, 3],
                                 'right_val': [1, 1, 3]})
        assert_frame_equal(result, expected)

    def test_valid_allow_exact_matches(self):

        trades = self.trades
        quotes = self.quotes

        with self.assertRaises(MergeError):
            merge_asof(trades, quotes,
                       on='time',
                       by='ticker',
                       allow_exact_matches='foo')

    def test_valid_tolerance(self):

        trades = self.trades
        quotes = self.quotes

        # dti
        merge_asof(trades, quotes,
                   on='time',
                   by='ticker',
                   tolerance=Timedelta('1s'))

        # integer
        merge_asof(trades.reset_index(), quotes.reset_index(),
                   on='index',
                   by='ticker',
                   tolerance=1)

        # incompat
        with self.assertRaises(MergeError):
            merge_asof(trades, quotes,
                       on='time',
                       by='ticker',
                       tolerance=1)

        # invalid
        with self.assertRaises(MergeError):
            merge_asof(trades.reset_index(), quotes.reset_index(),
                       on='index',
                       by='ticker',
                       tolerance=1.0)

        # invalid negative
        with self.assertRaises(MergeError):
            merge_asof(trades, quotes,
                       on='time',
                       by='ticker',
                       tolerance=-Timedelta('1s'))

        with self.assertRaises(MergeError):
            merge_asof(trades.reset_index(), quotes.reset_index(),
                       on='index',
                       by='ticker',
                       tolerance=-1)

    def test_non_sorted(self):

        trades = self.trades.sort_values('time', ascending=False)
        quotes = self.quotes.sort_values('time', ascending=False)

        # we require that we are already sorted on time & quotes
        self.assertFalse(trades.time.is_monotonic)
        self.assertFalse(quotes.time.is_monotonic)
        with self.assertRaises(ValueError):
            merge_asof(trades, quotes,
                       on='time',
                       by='ticker')

        trades = self.trades.sort_values('time')
        self.assertTrue(trades.time.is_monotonic)
        self.assertFalse(quotes.time.is_monotonic)
        with self.assertRaises(ValueError):
            merge_asof(trades, quotes,
                       on='time',
                       by='ticker')

        quotes = self.quotes.sort_values('time')
        self.assertTrue(trades.time.is_monotonic)
        self.assertTrue(quotes.time.is_monotonic)

        # ok, though has dupes
        merge_asof(trades, self.quotes,
                   on='time',
                   by='ticker')

    def test_tolerance(self):

        trades = self.trades
        quotes = self.quotes

        result = merge_asof(trades, quotes,
                            on='time',
                            by='ticker',
                            tolerance=Timedelta('1day'))
        expected = self.tolerance
        assert_frame_equal(result, expected)

    def test_tolerance_tz(self):
        # GH 14844
        left = pd.DataFrame(
            {'date': pd.DatetimeIndex(start=pd.to_datetime('2016-01-02'),
                                      freq='D', periods=5,
                                      tz=pytz.timezone('UTC')),
             'value1': np.arange(5)})
        right = pd.DataFrame(
            {'date': pd.DatetimeIndex(start=pd.to_datetime('2016-01-01'),
                                      freq='D', periods=5,
                                      tz=pytz.timezone('UTC')),
             'value2': list("ABCDE")})
        result = pd.merge_asof(left, right, on='date',
                               tolerance=pd.Timedelta('1 day'))

        expected = pd.DataFrame(
            {'date': pd.DatetimeIndex(start=pd.to_datetime('2016-01-02'),
                                      freq='D', periods=5,
                                      tz=pytz.timezone('UTC')),
             'value1': np.arange(5),
             'value2': list("BCDEE")})
        assert_frame_equal(result, expected)

    def test_allow_exact_matches(self):

        result = merge_asof(self.trades, self.quotes,
                            on='time',
                            by='ticker',
                            allow_exact_matches=False)
        expected = self.allow_exact_matches
        assert_frame_equal(result, expected)

    def test_allow_exact_matches_and_tolerance(self):

        result = merge_asof(self.trades, self.quotes,
                            on='time',
                            by='ticker',
                            tolerance=Timedelta('100ms'),
                            allow_exact_matches=False)
        expected = self.allow_exact_matches_and_tolerance
        assert_frame_equal(result, expected)

    def test_allow_exact_matches_and_tolerance2(self):
        # GH 13695
        df1 = pd.DataFrame({
            'time': pd.to_datetime(['2016-07-15 13:30:00.030']),
            'username': ['bob']})
        df2 = pd.DataFrame({
            'time': pd.to_datetime(['2016-07-15 13:30:00.000',
                                    '2016-07-15 13:30:00.030']),
            'version': [1, 2]})

        result = pd.merge_asof(df1, df2, on='time')
        expected = pd.DataFrame({
            'time': pd.to_datetime(['2016-07-15 13:30:00.030']),
            'username': ['bob'],
            'version': [2]})
        assert_frame_equal(result, expected)

        result = pd.merge_asof(df1, df2, on='time', allow_exact_matches=False)
        expected = pd.DataFrame({
            'time': pd.to_datetime(['2016-07-15 13:30:00.030']),
            'username': ['bob'],
            'version': [1]})
        assert_frame_equal(result, expected)

        result = pd.merge_asof(df1, df2, on='time', allow_exact_matches=False,
                               tolerance=pd.Timedelta('10ms'))
        expected = pd.DataFrame({
            'time': pd.to_datetime(['2016-07-15 13:30:00.030']),
            'username': ['bob'],
            'version': [np.nan]})
        assert_frame_equal(result, expected)

    def test_allow_exact_matches_and_tolerance3(self):
        # GH 13709
        df1 = pd.DataFrame({
            'time': pd.to_datetime(['2016-07-15 13:30:00.030',
                                   '2016-07-15 13:30:00.030']),
            'username': ['bob', 'charlie']})
        df2 = pd.DataFrame({
            'time': pd.to_datetime(['2016-07-15 13:30:00.000',
                                    '2016-07-15 13:30:00.030']),
            'version': [1, 2]})

        result = pd.merge_asof(df1, df2, on='time', allow_exact_matches=False,
                               tolerance=pd.Timedelta('10ms'))
        expected = pd.DataFrame({
            'time': pd.to_datetime(['2016-07-15 13:30:00.030',
                                    '2016-07-15 13:30:00.030']),
            'username': ['bob', 'charlie'],
            'version': [np.nan, np.nan]})
        assert_frame_equal(result, expected)

    def test_by_int(self):
        # we specialize by type, so test that this is correct
        df1 = pd.DataFrame({
            'time': pd.to_datetime(['20160525 13:30:00.020',
                                    '20160525 13:30:00.030',
                                    '20160525 13:30:00.040',
                                    '20160525 13:30:00.050',
                                    '20160525 13:30:00.060']),
            'key': [1, 2, 1, 3, 2],
            'value1': [1.1, 1.2, 1.3, 1.4, 1.5]},
            columns=['time', 'key', 'value1'])

        df2 = pd.DataFrame({
            'time': pd.to_datetime(['20160525 13:30:00.015',
                                    '20160525 13:30:00.020',
                                    '20160525 13:30:00.025',
                                    '20160525 13:30:00.035',
                                    '20160525 13:30:00.040',
                                    '20160525 13:30:00.055',
                                    '20160525 13:30:00.060',
                                    '20160525 13:30:00.065']),
            'key': [2, 1, 1, 3, 2, 1, 2, 3],
            'value2': [2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8]},
            columns=['time', 'key', 'value2'])

        result = pd.merge_asof(df1, df2, on='time', by='key')

        expected = pd.DataFrame({
            'time': pd.to_datetime(['20160525 13:30:00.020',
                                    '20160525 13:30:00.030',
                                    '20160525 13:30:00.040',
                                    '20160525 13:30:00.050',
                                    '20160525 13:30:00.060']),
            'key': [1, 2, 1, 3, 2],
            'value1': [1.1, 1.2, 1.3, 1.4, 1.5],
            'value2': [2.2, 2.1, 2.3, 2.4, 2.7]},
            columns=['time', 'key', 'value1', 'value2'])

        assert_frame_equal(result, expected)

    def test_on_float(self):
        # mimics how to determine the minimum-price variation
        df1 = pd.DataFrame({
            'price': [5.01, 0.0023, 25.13, 340.05, 30.78, 1040.90, 0.0078],
            'symbol': list("ABCDEFG")},
            columns=['symbol', 'price'])

        df2 = pd.DataFrame({
            'price': [0.0, 1.0, 100.0],
            'mpv': [0.0001, 0.01, 0.05]},
            columns=['price', 'mpv'])

        df1 = df1.sort_values('price').reset_index(drop=True)

        result = pd.merge_asof(df1, df2, on='price')

        expected = pd.DataFrame({
            'symbol': list("BGACEDF"),
            'price': [0.0023, 0.0078, 5.01, 25.13, 30.78, 340.05, 1040.90],
            'mpv': [0.0001, 0.0001, 0.01, 0.01, 0.01, 0.05, 0.05]},
            columns=['symbol', 'price', 'mpv'])

        assert_frame_equal(result, expected)

    def test_on_float_by_int(self):
        # type specialize both "by" and "on" parameters
        df1 = pd.DataFrame({
            'symbol': list("AAABBBCCC"),
            'exch': [1, 2, 3, 1, 2, 3, 1, 2, 3],
            'price': [3.26, 3.2599, 3.2598, 12.58, 12.59,
                      12.5, 378.15, 378.2, 378.25]},
            columns=['symbol', 'exch', 'price'])

        df2 = pd.DataFrame({
            'exch': [1, 1, 1, 2, 2, 2, 3, 3, 3],
            'price': [0.0, 1.0, 100.0, 0.0, 5.0, 100.0, 0.0, 5.0, 1000.0],
            'mpv': [0.0001, 0.01, 0.05, 0.0001, 0.01, 0.1, 0.0001, 0.25, 1.0]},
            columns=['exch', 'price', 'mpv'])

        df1 = df1.sort_values('price').reset_index(drop=True)
        df2 = df2.sort_values('price').reset_index(drop=True)

        result = pd.merge_asof(df1, df2, on='price', by='exch')

        expected = pd.DataFrame({
            'symbol': list("AAABBBCCC"),
            'exch': [3, 2, 1, 3, 1, 2, 1, 2, 3],
            'price': [3.2598, 3.2599, 3.26, 12.5, 12.58,
                      12.59, 378.15, 378.2, 378.25],
            'mpv': [0.0001, 0.0001, 0.01, 0.25, 0.01, 0.01, 0.05, 0.1, 0.25]},
            columns=['symbol', 'exch', 'price', 'mpv'])

        assert_frame_equal(result, expected)


if __name__ == '__main__':
    nose.runmodule(argv=[__file__, '-vvs', '-x', '--pdb', '--pdb-failure'],
                   exit=False)
