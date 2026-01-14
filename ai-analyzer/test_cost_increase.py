import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from cost_analyzer import AWSCostDataExtractor

class TestCostAnalyzer(unittest.TestCase):
    @patch('boto3.client')
    def test_check_cost_increases(self, mock_boto_client):
        # Mock CE client
        mock_ce = MagicMock()
        mock_boto_client.return_value = mock_ce
        
        # Mock response for get_cost_and_usage
        mock_ce.get_cost_and_usage.return_value = {
            'ResultsByTime': [
                {
                    'TimePeriod': {'Start': '2026-01-10', 'End': '2026-01-11'},
                    'Groups': [
                        {'Keys': ['Amazon EC2'], 'Metrics': {'UnblendedCost': {'Amount': '12.0'}}},
                        {'Keys': ['Amazon S3'], 'Metrics': {'UnblendedCost': {'Amount': '5.0'}}}
                    ]
                },
                {
                    'TimePeriod': {'Start': '2026-01-11', 'End': '2026-01-12'},
                    'Groups': [
                        {'Keys': ['Amazon EC2'], 'Metrics': {'UnblendedCost': {'Amount': '14.0'}}},
                        {'Keys': ['Amazon S3'], 'Metrics': {'UnblendedCost': {'Amount': '4.0'}}}
                    ]
                }
            ]
        }
        
        extractor = AWSCostDataExtractor('ak', 'sk')
        alerts = extractor.check_cost_increases()
        
        # Verify alerts
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]['service'], 'Amazon EC2')
        self.assertEqual(alerts[0]['yesterday_cost'], 12.0)
        self.assertEqual(alerts[0]['today_cost'], 14.0)
        self.assertEqual(alerts[0]['increase'], 2.0)
        self.assertAlmostEqual(alerts[0]['percent_increase'], 16.666666666666664)

if __name__ == '__main__':
    unittest.main()
