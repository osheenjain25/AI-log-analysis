import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add the directory to sys.path to import the module
sys.path.append('/home/user/.gemini/antigravity/scratch/ai-analyzer')

from cost_analyzer import analyze_cost_pipeline

class TestCostAnalyzer(unittest.TestCase):

    @patch('cost_analyzer.AWSCostDataExtractor')
    @patch('cost_analyzer.AWSCostLLMAnalyzer')
    def test_analyze_cost_pipeline_returns_charts(self, MockAnalyzer, MockExtractor):
        # Setup Mock Extractor
        mock_extractor_instance = MockExtractor.return_value
        mock_extractor_instance.extract_cost_data_by_service_and_usage.return_value = {'some': 'data'}
        
        mock_partitioned_data = {
            'Amazon Elastic Compute Cloud - Compute': {
                'service_name': 'Amazon Elastic Compute Cloud - Compute',
                'metrics_summary': {'total_cost': 1000.0},
                'time_series': [
                    {'date': '2023-01-01', 'unblended_cost': 1000.0},
                    {'date': '2023-01-02', 'unblended_cost': 1200.0},
                    {'date': '2023-01-03', 'unblended_cost': 1100.0},
                    {'date': '2023-01-04', 'unblended_cost': 1300.0}
                ]
            },
            'Amazon Simple Storage Service': {
                'service_name': 'Amazon Simple Storage Service',
                'metrics_summary': {'total_cost': 10.0},
                'time_series': [
                    {'date': '2023-01-01', 'unblended_cost': 10.0},
                    {'date': '2023-01-02', 'unblended_cost': 10.0},
                    {'date': '2023-01-03', 'unblended_cost': 10.0},
                    {'date': '2023-01-04', 'unblended_cost': 10.0}
                ]
            }
        }
        mock_extractor_instance.partition_data_by_service.return_value = mock_partitioned_data

        # Setup Mock Analyzer
        mock_analyzer_instance = MockAnalyzer.return_value
        # Mock analyze_batch to return a tuple (all_analyses, final_report)
        mock_analyzer_instance.analyze_batch.return_value = (
            {"Test": "analysis"}, 
            "Final Report"
        )

        # Run pipeline
        report, chart_data, total_cost, metadata = analyze_cost_pipeline(
            aws_access_key="fake",
            aws_secret_key="fake",
            api_key="fake",
            api_url="fake",
            model="fake",
            target_services=["S3"]
        )
        
        # Verify Report
        self.assertEqual(report, "Final Report")
        
        # Verify Chart Data
        self.assertIn('stacked_bar_data', chart_data)
        self.assertIn('top_trends', chart_data)
        self.assertTrue(len(chart_data['stacked_bar_data']) > 0)
        self.assertTrue(len(chart_data['top_trends']) > 0)

    @patch('cost_analyzer.AWSCostDataExtractor')
    @patch('cost_analyzer.AWSCostLLMAnalyzer')
    def test_analyze_cost_pipeline_analyzes_zero_cost_if_targeted(self, MockAnalyzer, MockExtractor):
        # Setup Mock Extractor
        mock_extractor_instance = MockExtractor.return_value
        mock_extractor_instance.extract_cost_data_by_service_and_usage.return_value = {'some': 'data'}
        
        mock_partitioned_data = {
            'Amazon Simple Storage Service': {
                'service_name': 'Amazon Simple Storage Service',
                'metrics_summary': {'total_cost': 0.0}, # Zero cost
                'time_series': [{'date': '2023-01-01', 'unblended_cost': 0.0}]
            }
        }
        mock_extractor_instance.partition_data_by_service.return_value = mock_partitioned_data

        # Setup Mock Analyzer
        mock_analyzer_instance = MockAnalyzer.return_value
        # Mock analyze_batch to return a tuple (all_analyses, final_report)
        mock_analyzer_instance.analyze_batch.return_value = (
            {"Amazon Simple Storage Service": "analysis"}, 
            "Final Report"
        )

        # Run pipeline with target_services=['S3']
        report, chart_data, total_cost, metadata = analyze_cost_pipeline(
            aws_access_key='fake', 
            aws_secret_key='fake', 
            api_key='fake', 
            api_url='fake', 
            model='fake', 
            target_services=['S3']
        )

        # Verify it WAS analyzed despite 0 cost because it was targeted
        # Check if analyze_batch was called with the service
        # analyze_batch is called with a list of service data dicts
        self.assertTrue(mock_analyzer_instance.analyze_batch.called)
        args, _ = mock_analyzer_instance.analyze_batch.call_args
        services_to_analyze = args[0]
        
        service_names = [s['service_name'] for s in services_to_analyze]
        print(f"Services analyzed (zero cost test): {service_names}")
        self.assertIn('Amazon Simple Storage Service', service_names)

if __name__ == '__main__':
    unittest.main()
