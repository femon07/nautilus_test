
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
import pandas as pd
from pathlib import Path
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.dukascopy_loader import load_dukascopy_data

class TestDukascopyLoader(unittest.TestCase):
    def setUp(self):
        self.symbol = "EURUSD"
        self.start_date = datetime(2023, 1, 1, tzinfo=timezone.utc)
        self.end_date = datetime(2023, 1, 2, tzinfo=timezone.utc)
        # Expected filename format: %Y%m%d-%H%M
        self.expected_filename = "EURUSD_20230101-0000_20230102-0000.csv"
        self.data_dir = Path("./data")

    @patch('utils.dukascopy_loader.Path.exists')
    @patch('utils.dukascopy_loader.pd.read_csv')
    def test_load_cached_data(self, mock_read_csv, mock_exists):
        """Test that cached data is used if it exists with correct filename"""
        mock_exists.return_value = True
        
        # Mock DataFrame
        mock_df = pd.DataFrame({
            'timestamp': ['2023-01-01 00:00:00+00:00'],
            'open': [1.0], 'high': [1.0], 'low': [1.0], 'close': [1.0], 'volume': [100]
        })
        mock_read_csv.return_value = mock_df
        
        df = load_dukascopy_data(self.symbol, self.start_date, self.end_date)
        
        # Check path construction
        expected_path = self.data_dir / self.expected_filename
        # Path object comparison might be tricky with mocks, but we can verify calls
        # We can check if exists was called on the correct path object if we mock Path constructor, 
        # but simpler is to trust the logic if file name is correct.
        
        # Since we mocked path.exists on any Path instance (if patch target is correct), 
        # let's verify read_csv was called.
        mock_read_csv.assert_called_once()
        call_args = mock_read_csv.call_args[0][0]
        self.assertTrue(str(call_args).endswith(self.expected_filename))
        
        # Verify UTC conversion
        self.assertEqual(df['timestamp'].dt.tz, timezone.utc)

    @patch('utils.dukascopy_loader._download_hour')
    @patch('utils.dukascopy_loader._resample_to_m1')
    @patch('utils.dukascopy_loader.pd.DataFrame.to_csv')
    @patch('utils.dukascopy_loader.Path.exists')
    def test_download_loop_exclusive_end_date(self, mock_exists, mock_to_csv, mock_resample, mock_download):
        """Test that download loop respects exclusive end_date"""
        mock_exists.return_value = False
        mock_download.return_value = [] # Return empty list of ticks
        
        # Mock resample to return dummy DF
        mock_resample.return_value = pd.DataFrame({'dummy': [1]})
        
        # Run with short range: 1 hour difference
        # start: 00:00, end: 01:00 -> should download 00:00 only (1 hour)
        end_date_short = datetime(2023, 1, 1, 1, tzinfo=timezone.utc)
        
        # We need to mock _download_hour to return something otherwise it raises ValueError "empty data"
        # Wait, if _download_hour returns [], the loop continues.
        # But `if not all_ticks: raise ValueError`
        # So we MUST return some ticks.
        mock_download.return_value = [{'timestamp': self.start_date, 'ask': 1, 'bid': 1, 'ask_volume': 1, 'bid_volume': 1}]
        
        load_dukascopy_data(self.symbol, self.start_date, end_date_short)
        
        # Should be called exactly once for 00:00 (start_date)
        mock_download.assert_called_once()
        args, _ = mock_download.call_args
        # args[1] is 'current' time
        self.assertEqual(args[1], self.start_date.replace(tzinfo=None))

    @patch('utils.dukascopy_loader._download_hour')
    @patch('utils.dukascopy_loader._resample_to_m1')
    @patch('utils.dukascopy_loader.pd.DataFrame.to_csv')
    @patch('utils.dukascopy_loader.Path.exists')
    def test_filename_generation_dates(self, mock_exists, mock_to_csv, mock_resample, mock_download):
        """Test the filename includes the correct start and end dates"""
        mock_exists.return_value = False
        mock_download.return_value = [{'timestamp': self.start_date}]
        mock_resample.return_value = pd.DataFrame([1])
        
        load_dukascopy_data(self.symbol, self.start_date, self.end_date)
        
        # to_csv should be called with correct path
        mock_to_csv.assert_called_once()
        args, _ = mock_to_csv.call_args
        save_path = str(args[0])
        self.assertTrue(save_path.endswith(self.expected_filename))

    @patch('utils.dukascopy_loader._download_hour')
    @patch('utils.dukascopy_loader._resample_to_m1')
    @patch('utils.dukascopy_loader.pd.DataFrame.to_csv')
    @patch('utils.dukascopy_loader.Path.exists')
    def test_jst_timezone_input(self, mock_exists, mock_to_csv, mock_resample, mock_download):
        """Test that JST input is correctly converted to UTC for filename generation"""
        mock_exists.return_value = False
        mock_download.return_value = [{'timestamp': self.start_date}]
        mock_resample.return_value = pd.DataFrame([1])
        
        # JST Timezone (UTC+9)
        jst = timezone(timedelta(hours=9))
        start_jst = datetime(2023, 1, 1, 9, 0, tzinfo=jst) # 2023-01-01 00:00 UTC
        end_jst = datetime(2023, 1, 2, 9, 0, tzinfo=jst)   # 2023-01-02 00:00 UTC
        
        load_dukascopy_data(self.symbol, start_jst, end_jst)
        
        # Check if the filename corresponds to UTC time
        # 2023-01-01 09:00 JST -> 2023-01-01 00:00 UTC
        expected_utc_filename = "EURUSD_20230101-0000_20230102-0000.csv"
        
        mock_to_csv.assert_called_once()
        args, _ = mock_to_csv.call_args
        save_path = str(args[0])
        self.assertTrue(save_path.endswith(expected_utc_filename))

if __name__ == '__main__':
    unittest.main()
