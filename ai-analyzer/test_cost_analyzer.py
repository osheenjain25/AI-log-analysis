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
                    {'date': '2023-01-01', 'blended_cost': 1000.0},
                    {'date': '2023-01-02', 'blended_cost': 1200.0}
                ]
            },
            'Amazon Simple Storage Service': {
                'service_name': 'Amazon Simple Storage Service',
                'metrics_summary': {'total_cost': 10.0},
                'time_series': [{'date': '2023-01-01', 'blended_cost': 10.0}]
            }
        }
        mock_extractor_instance.partition_data_by_service.return_value = mock_partitioned_data

        # Setup Mock Analyzer
        mock_analyzer_instance = MockAnalyzer.return_value
        mock_analyzer_instance.analyze_single_service.return_value = {'service_name': 'Test', 'analysis': 'result'}
        mock_analyzer_instance.consolidate_analyses.return_value = "Final Report"

        # Run pipeline
        report, chart_data = analyze_cost_pipeline(
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
                'time_series': [{'date': '2023-01-01', 'blended_cost': 0.0}]
            }
        }
        mock_extractor_instance.partition_data_by_service.return_value = mock_partitioned_data

        # Setup Mock Analyzer
        mock_analyzer_instance = MockAnalyzer.return_value
        mock_analyzer_instance.analyze_single_service.return_value = {'service_name': 'Test', 'analysis': 'result'}
        mock_analyzer_instance.consolidate_analyses.return_value = "Final Report"

        # Run pipeline with target_services=['S3']
        report, chart_data = analyze_cost_pipeline(
            aws_access_key='fake', 
            aws_secret_key='fake', 
            api_key='fake', 
            api_url='fake', 
            model='fake', 
            target_services=['S3']
        )

        # Verify it WAS analyzed despite 0 cost because it was targeted
        called_services = []
        for call in mock_analyzer_instance.analyze_single_service.call_args_list:
            args, _ = call
            called_services.append(args[0]['service_name'])
            
        print(f"Services analyzed (zero cost test): {called_services}")
        self.assertIn('Amazon Simple Storage Service', called_services)

if __name__ == '__main__':
    unittest.main()
