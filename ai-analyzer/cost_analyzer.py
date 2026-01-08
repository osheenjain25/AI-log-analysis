# COST_ANALYZER.PY

import json
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import boto3
import google.generativeai as genai
import pandas as pd
from prompts import SERVICE_ANALYSIS_PROMPT, COMBINER_ANALYSIS_PROMPT

class AWSCostDataExtractor:
    """ 
    Connects to AWS Cost Explorer, fetches cost and usage data,
    processes it, and partitions it by service for further analysis.
    """
    def __init__(self, aws_access_key_id: str, aws_secret_access_key: str, region_name: str = 'us-east-1'):
        self.ce_client = boto3.client(
            'ce',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name
        )
        self.granularity = 'DAILY'
        self.start_date = None
        self.end_date = None
        self.analysis_period_days = 30

    def set_time_period(self, days_back: int = 30):
        """Set the time period for analysis."""
        self.analysis_period_days = days_back
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days_back)
        self.start_date = start_date.strftime('%Y-%m-%d')
        self.end_date = end_date.strftime('%Y-%m-%d')

    def extract_cost_data_by_service_and_usage(self) -> Dict:
        """Extract cost data grouped by SERVICE and USAGE_TYPE"""
        try:
            response = self.ce_client.get_cost_and_usage(
                TimePeriod={'Start': self.start_date, 'End': self.end_date},
                Granularity=self.granularity,
                Metrics=['BlendedCost', 'UsageQuantity', 'UnblendedCost'],
                GroupBy=[
                    {'Type': 'DIMENSION', 'Key': 'SERVICE'},
                    {'Type': 'DIMENSION', 'Key': 'USAGE_TYPE'}
                ]
            )
            return self._process_response(response, 'service_usage')
        except Exception as e:
            print(f"Error fetching cost data: {e}")
            return {}

    def _process_response(self, response: Dict, data_type: str) -> Dict:
        """Process API response into a structured format."""
        processed_data = {
            'data_type': data_type,
            'analysis_config': {
                'granularity': self.granularity,
                'period_days': self.analysis_period_days,
                'start_date': self.start_date,
                'end_date': self.end_date
            },
            'results_by_time': [],
            'summary': {
                'total_cost': 0,
                'total_usage': 0,
                'services': set()
            }
        }
        
        for result in response.get('ResultsByTime', []):
            time_period = result.get('TimePeriod', {})
            period_data = {
                'start_date': time_period.get('Start'),
                'end_date': time_period.get('End'),
                'groups': []
            }
            
            for group in result.get('Groups', []):
                group_keys = group.get('Keys', [])
                metrics = group.get('Metrics', {})
                service = group_keys[0] if group_keys else 'Unknown'
                processed_data['summary']['services'].add(service)
                
                group_data = {
                    'service': service,
                    'secondary_dimension': group_keys[1] if len(group_keys) > 1 else None,
                    'blended_cost': float(metrics.get('BlendedCost', {}).get('Amount', 0)),
                    'usage_quantity': float(metrics.get('UsageQuantity', {}).get('Amount', 0)),
                    'usage_unit': metrics.get('UsageQuantity', {}).get('Unit', 'N/A')
                }
                
                period_data['groups'].append(group_data)
                processed_data['summary']['total_cost'] += group_data['blended_cost']
                processed_data['summary']['total_usage'] += group_data['usage_quantity']
            
            processed_data['results_by_time'].append(period_data)
        
        processed_data['summary']['services'] = list(processed_data['summary']['services'])
        return processed_data

    def partition_data_by_service(self, data: Dict) -> Dict:
        """Partition data by service for individual LLM analysis."""
        if not data:
            return {}
        
        partitioned_data = {}
        
        for time_result in data.get('results_by_time', []):
            for group in time_result.get('groups', []):
                service = group['service']
                
                if service not in partitioned_data:
                    partitioned_data[service] = {
                        'service_name': service,
                        'data_type': data['data_type'],
                        'analysis_period': f'{self.analysis_period_days}_days',
                        'time_series': [],
                        'metrics_summary': {
                            'total_cost': 0, 'total_usage': 0, 'peak_usage': 0
                        }
                    }
                
                partitioned_data[service]['time_series'].append({
                    'date': time_result['start_date'],
                    'secondary_dimension': group['secondary_dimension'],
                    'blended_cost': group['blended_cost'],
                    'usage_quantity': group['usage_quantity'],
                    'usage_unit': group['usage_unit']
                })
                
                partitioned_data[service]['metrics_summary']['total_cost'] += group['blended_cost']
                partitioned_data[service]['metrics_summary']['total_usage'] += group['usage_quantity']
                partitioned_data[service]['metrics_summary']['peak_usage'] = max(
                    partitioned_data[service]['metrics_summary']['peak_usage'], group['usage_quantity']
                )
        
        return partitioned_data

class AWSCostLLMAnalyzer:
    """ 
    Uses Gemini to analyze partitioned AWS cost data.
    """
    def __init__(self, gemini_api_key: str):
        genai.configure(api_key=gemini_api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')

    def analyze_single_service(self, service_data: Dict) -> Dict:
        """Analyze a single service partition with GEMINI."""
        try:
            data_json = json.dumps(service_data, indent=2)
            full_prompt = f"{SERVICE_ANALYSIS_PROMPT}\n\n{data_json}"
            
            response = self.model.generate_content(full_prompt)
            response_text = response.text
            
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.rfind("```")
                response_text = response_text[json_start:json_end]
            
            return json.loads(response_text)
        except Exception as e:
            print(f"Error analyzing service {service_data.get('service_name')}: {e}")
            return {
                "service_name": service_data.get('service_name', 'Unknown'),
                "analysis_error": str(e)
            }

    def consolidate_analyses(self, all_analyses: List[Dict]) -> str:
        """Consolidate all individual analyses into a text report."""
        if not all_analyses:
            return "No analyses to consolidate."
        
        analyses_json = json.dumps(all_analyses, indent=2)
        full_prompt = f"{COMBINER_ANALYSIS_PROMPT}\n\n{analyses_json}"
        
        try:
            response = self.model.generate_content(full_prompt)
            return response.text.replace("```markdown", "").replace("```", "").strip()
        except Exception as e:
            return f"Error in consolidation: {str(e)}"

def analyze_cost_pipeline(aws_access_key: str, aws_secret_key: str, gemini_api_key: str, days: int = 30) -> str:
    """
    Orchestrates the cost analysis pipeline.
    Returns the final markdown report.
    """
    # 1. Extract Data
    extractor = AWSCostDataExtractor(aws_access_key, aws_secret_key)
    extractor.set_time_period(days)
    
    raw_data = extractor.extract_cost_data_by_service_and_usage()
    if not raw_data:
        return "Failed to fetch AWS cost data. Please check your credentials."
        
    partitioned_data = extractor.partition_data_by_service(raw_data)
    
    # 2. Analyze with LLM
    analyzer = AWSCostLLMAnalyzer(gemini_api_key)
    all_analyses = []
    
    # Filter for top services by cost to save time/tokens (optional but good practice)
    # For now, we'll analyze all services with > $0 cost
    
    sorted_services = sorted(
        partitioned_data.values(), 
        key=lambda x: x['metrics_summary']['total_cost'], 
        reverse=True
    )
    
    # Limit to top 10 services to avoid timeouts
    top_services = sorted_services[:10]
    
    for service_data in top_services:
        if service_data['metrics_summary']['total_cost'] > 0:
            analysis = analyzer.analyze_single_service(service_data)
            all_analyses.append(analysis)
            time.sleep(1) # Rate limiting
            
    # 3. Consolidate
    final_report = analyzer.consolidate_analyses(all_analyses)
    
    return final_report
