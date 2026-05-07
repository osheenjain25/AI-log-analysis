
import sys
import os
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

# Add current directory to path
sys.path.append(os.getcwd())

from cost_analyzer import HuaweiCostDataSource

class MockHuaweiCostDataSource(HuaweiCostDataSource):
    def _create_client(self):
        return MagicMock()

class TestHuaweiCostDataSource(unittest.TestCase):
    def setUp(self):
        self.ds = MockHuaweiCostDataSource(ak="test", sk="test", region="cn-north-1")
        # Client is already mocked by _create_client override
        
    def test_aggregation_weekly(self):
        print("\n--- Testing Huawei Weekly Aggregation ---")
        self.ds.set_time_period(days_back=30)
        
        # Mock _fetch_month_data to populate all_records with daily data
        # We'll patch _fetch_month_data to avoid API calls and just fill records
        with patch.object(self.ds, '_fetch_month_data') as mock_fetch:
            def side_effect(cycle, all_records):
                # Generate records only for the requested cycle
                year, month = map(int, cycle.split('-'))
                # Generate data for this month (simple 1st to 28th to be safe)
                for day in range(1, 29):
                    date_str = f"{year:04d}-{month:02d}-{day:02d}"
                    # Check if date is within start/end date range of the DS
                    if date_str < self.ds.start_date or date_str > self.ds.end_date:
                        continue
                        
                    record = MagicMock()
                    record.cloud_service_type_name = "Elastic Cloud Server"
                    record.region_name = "cn-north-1"
                    record.consume_amount = 10.0
                    record.official_amount = 10.0
                    record.measure_id = "Hrs"
                    record.bill_date = date_str
                    all_records.append(record)
            
            mock_fetch.side_effect = side_effect
            
            # Run extraction with WEEKLY granularity
            data = self.ds.extract_cost_data_by_service_and_usage(granularity='WEEKLY')
            
            points = len(data['results_by_time'])
            total_cost = data['summary']['total_cost']
            
            print(f"Weekly Points: {points}")
            print(f"Total Cost: {total_cost}")
            
            self.assertTrue(points <= 6, f"Expected <= 6 weekly points, got {points}")
            self.assertAlmostEqual(total_cost, 280.0)
            self.assertEqual(data['analysis_config']['granularity'], 'WEEKLY')

    def test_aggregation_monthly(self):
        print("\n--- Testing Huawei Monthly Aggregation ---")
        self.ds.set_time_period(days_back=60)
        
        with patch.object(self.ds, '_fetch_month_data') as mock_fetch:
            def side_effect(cycle, all_records):
                # We need to be careful about cycles. The code iterates cycles.
                # Let's just append data based on the cycle passed
                year, month = map(int, cycle.split('-'))
                # Add a few records for this month
                record = MagicMock()
                record.cloud_service_type_name = "Elastic Cloud Server"
                record.region_name = "cn-north-1"
                record.consume_amount = 100.0
                record.official_amount = 100.0
                record.measure_id = "Hrs"
                record.bill_date = f"{cycle}-15" # Mid-month
                all_records.append(record)
            
            mock_fetch.side_effect = side_effect
            
            data = self.ds.extract_cost_data_by_service_and_usage(granularity='MONTHLY')
            
            points = len(data['results_by_time'])
            total_cost = data['summary']['total_cost']
            
            print(f"Monthly Points: {points}")
            print(f"Total Cost: {total_cost}")
            
            self.assertTrue(points <= 3, f"Expected <= 3 monthly points, got {points}")
            self.assertEqual(data['analysis_config']['granularity'], 'MONTHLY')

if __name__ == '__main__':
    unittest.main()
