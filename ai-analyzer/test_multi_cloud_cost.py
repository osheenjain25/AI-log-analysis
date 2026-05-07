import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add the parent directory to sys.path to import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cost_analyzer import analyze_cost_pipeline, GCPCostDataSource, HuaweiCostDataSource

class TestMultiCloudCostAnalyzer(unittest.TestCase):

    @patch('cost_analyzer.AWSCostLLMAnalyzer')
    def test_gcp_cost_pipeline(self, MockLLMAnalyzer):
        # Mock LLM Analyzer
        mock_llm_instance = MockLLMAnalyzer.return_value
        mock_llm_instance.analyze_batch.return_value = ({"GCP Service": "analysis"}, "GCP Analysis Report")

        # Run pipeline with provider='gcp'
        report, chart_data, total_cost, metadata = analyze_cost_pipeline(
            aws_access_key="dummy", 
            aws_secret_key="dummy", 
            api_key="dummy", 
            api_url="dummy", 
            model="dummy", 
            provider='gcp'
        )

        # Assertions
        self.assertIn("GCP Analysis Report", report)
        self.assertTrue(total_cost > 0) # Simulated data should return cost > 0
        self.assertTrue(metadata['is_complete'])

    @patch('cost_analyzer.AWSCostLLMAnalyzer')
    def test_huawei_cost_pipeline(self, MockLLMAnalyzer):
        # Mock LLM Analyzer
        mock_llm_instance = MockLLMAnalyzer.return_value
        mock_llm_instance.analyze_batch.return_value = ({"Huawei Service": "analysis"}, "Huawei Analysis Report")

        # Run pipeline with provider='huawei'
        report, chart_data, total_cost, metadata = analyze_cost_pipeline(
            aws_access_key="dummy", 
            aws_secret_key="dummy", 
            api_key="dummy", 
            api_url="dummy", 
            model="dummy", 
            provider='huawei'
        )

        # Assertions
        self.assertIn("Huawei Analysis Report", report)
        self.assertTrue(total_cost > 0) # Simulated data should return cost > 0
        self.assertTrue(metadata['is_complete'])

    def test_gcp_data_source(self):
        source = GCPCostDataSource()
        source.set_time_period(days_back=7)
        data = source.extract_cost_data_by_service_and_usage(granularity='DAILY')
        
        self.assertIn('results_by_time', data)
        self.assertTrue(len(data['results_by_time']) > 0)
        self.assertEqual(data['analysis_config']['granularity'], 'DAILY')
        self.assertTrue(data['summary']['total_cost'] > 0)
        self.assertIn('BigQuery', data['summary']['services'])

    def test_huawei_data_source(self):
        source = HuaweiCostDataSource()
        source.set_time_period(days_back=7)
        data = source.extract_cost_data_by_service_and_usage(granularity='DAILY')
        
        self.assertIn('results_by_time', data)
        self.assertTrue(len(data['results_by_time']) > 0)
        self.assertEqual(data['analysis_config']['granularity'], 'DAILY')
        self.assertTrue(data['summary']['total_cost'] > 0)
        self.assertIn('Elastic Cloud Server', data['summary']['services'])

if __name__ == '__main__':
    unittest.main()
