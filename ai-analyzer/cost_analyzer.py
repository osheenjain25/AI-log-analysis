# COST_ANALYZER.PY

import json
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import boto3
import pandas as pd
import pandas as pd
from prompts import SERVICE_ANALYSIS_PROMPT, COMBINER_ANALYSIS_PROMPT, BATCH_ANALYSIS_PROMPT
import google.generativeai as genai
import requests
import random

class CostDataSource:
    """Abstract base class for cost data sources."""
    def __init__(self):
        self.granularity = 'DAILY'
        self.start_date = None
        self.end_date = None
        self.analysis_period_days = 30

    def set_time_period(self, days_back: int = 30, start_date: str = None, end_date: str = None):
        """Set the time period for analysis."""
        if start_date and end_date:
            self.start_date = start_date
            self.end_date = end_date
            try:
                d1 = datetime.strptime(start_date, '%Y-%m-%d')
                d2 = datetime.strptime(end_date, '%Y-%m-%d')
                self.analysis_period_days = (d2 - d1).days
            except:
                self.analysis_period_days = 30
        else:
            self.analysis_period_days = days_back
            end_dt = datetime.now().date()
            start_dt = end_dt - timedelta(days=days_back)
            self.start_date = start_dt.strftime('%Y-%m-%d')
            self.end_date = end_dt.strftime('%Y-%m-%d')

    def extract_cost_data_by_service_and_usage(self, granularity: str = None) -> Dict:
        raise NotImplementedError

    def _aggregate_to_weekly(self, processed_data: Dict) -> Dict:
        """Aggregates daily data into weekly buckets."""
        if not processed_data.get('results_by_time'):
            return processed_data
            
        weekly_results = {} # week_start -> { service_usage -> {cost, usage} }
        
        for result in processed_data['results_by_time']:
            start_date = result['start_date']
            dt = datetime.strptime(start_date, '%Y-%m-%d')
            # Get the start of the week (Monday)
            week_start = (dt - timedelta(days=dt.weekday())).strftime('%Y-%m-%d')
            
            if week_start not in weekly_results:
                weekly_results[week_start] = {}
                
            for group in result['groups']:
                key = (group['service'], group.get('region', 'Unknown'))
                if key not in weekly_results[week_start]:
                    weekly_results[week_start][key] = {
                        'unblended_cost': 0.0,
                        'amortized_cost': 0.0,
                        'usage_quantity': 0.0,
                        'usage_unit': group.get('usage_unit', 'N/A')
                    }
                
                weekly_results[week_start][key]['unblended_cost'] += group['unblended_cost']
                weekly_results[week_start][key]['amortized_cost'] += group.get('amortized_cost', 0.0)
                weekly_results[week_start][key]['usage_quantity'] += group['usage_quantity']
                
        # Reconstruct results_by_time
        new_results = []
        for week_start in sorted(weekly_results.keys()):
            groups = []
            for (service, region), metrics in weekly_results[week_start].items():
                groups.append({
                    'service': service,
                    'secondary_dimension': region,
                    'region': region,
                    'unblended_cost': metrics['unblended_cost'],
                    'amortized_cost': metrics['amortized_cost'],
                    'usage_quantity': metrics['usage_quantity'],
                    'usage_unit': metrics['usage_unit']
                })
            
            new_results.append({
                'start_date': week_start,
                'end_date': (datetime.strptime(week_start, '%Y-%m-%d') + timedelta(days=7)).strftime('%Y-%m-%d'),
                'groups': groups
            })
            
        processed_data['results_by_time'] = new_results
        processed_data['analysis_config']['granularity'] = 'WEEKLY'
        return processed_data

    def _aggregate_to_monthly(self, processed_data: Dict) -> Dict:
        """Aggregates daily data into monthly buckets."""
        if not processed_data.get('results_by_time'):
            return processed_data
            
        monthly_results = {} # month_start -> { service_usage -> {cost, usage} }
        
        for result in processed_data['results_by_time']:
            start_date = result['start_date']
            dt = datetime.strptime(start_date, '%Y-%m-%d')
            # Get the first day of the month
            month_start = dt.replace(day=1).strftime('%Y-%m-%d')
            
            if month_start not in monthly_results:
                monthly_results[month_start] = {}
                
            for group in result['groups']:
                key = (group['service'], group.get('region', 'Unknown'))
                if key not in monthly_results[month_start]:
                    monthly_results[month_start][key] = {
                        'unblended_cost': 0.0,
                        'amortized_cost': 0.0,
                        'usage_quantity': 0.0,
                        'usage_unit': group.get('usage_unit', 'N/A')
                    }
                
                monthly_results[month_start][key]['unblended_cost'] += group['unblended_cost']
                monthly_results[month_start][key]['amortized_cost'] += group.get('amortized_cost', 0.0)
                monthly_results[month_start][key]['usage_quantity'] += group['usage_quantity']
                
        # Reconstruct results_by_time
        new_results = []
        for month_start in sorted(monthly_results.keys()):
            groups = []
            for (service, region), metrics in monthly_results[month_start].items():
                groups.append({
                    'service': service,
                    'secondary_dimension': region,
                    'region': region,
                    'unblended_cost': metrics['unblended_cost'],
                    'amortized_cost': metrics['amortized_cost'],
                    'usage_quantity': metrics['usage_quantity'],
                    'usage_unit': metrics['usage_unit']
                })
            
            # Calculate end of month
            dt = datetime.strptime(month_start, '%Y-%m-%d')
            if dt.month == 12:
                next_month = dt.replace(year=dt.year + 1, month=1)
            else:
                next_month = dt.replace(month=dt.month + 1)
            
            new_results.append({
                'start_date': month_start,
                'end_date': next_month.strftime('%Y-%m-%d'),
                'groups': groups
            })
            
        processed_data['results_by_time'] = new_results
        processed_data['analysis_config']['granularity'] = 'MONTHLY'
        return processed_data

class SimulatedAWSCostDataSource(CostDataSource):
    """Simulates AWS cost data for testing and demo purposes."""
    def __init__(self):
        super().__init__()
        self.services = ['AmazonEC2', 'AmazonRDS', 'AmazonS3', 'AWSLambda', 'AmazonCloudFront', 'AmazonDynamoDB']
        self.regions = ['us-east-1', 'us-west-2', 'eu-central-1']

    def extract_cost_data_by_service_and_usage(self, granularity: str = None) -> Dict:
        if granularity:
            self.granularity = granularity
            
        results = []
        current_date = datetime.strptime(self.start_date, '%Y-%m-%d')
        end_date = datetime.strptime(self.end_date, '%Y-%m-%d')
        
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            groups = []
            
            for service in self.services:
                # Generate random cost data
                base_cost = random.uniform(10.0, 100.0)
                if service == 'AmazonEC2':
                    base_cost *= 5
                elif service == 'AmazonRDS':
                    base_cost *= 3
                
                # Add some variance
                cost = base_cost * random.uniform(0.8, 1.2)
                amortized_cost = cost * 1.1
                usage = random.uniform(100, 1000)
                
                groups.append({
                    'service': service,
                    'region': random.choice(self.regions),
                    'secondary_dimension': 'RunInstances' if service == 'AmazonEC2' else 'Storage',
                    'unblended_cost': cost,
                    'amortized_cost': amortized_cost,
                    'usage_quantity': usage,
                    'usage_unit': 'Hrs' if service == 'AmazonEC2' else 'GB'
                })
            
            results.append({
                'start_date': date_str,
                'groups': groups
            })
            
            if self.granularity == 'DAILY':
                current_date += timedelta(days=1)
            elif self.granularity == 'WEEKLY':
                current_date += timedelta(weeks=1)
            elif self.granularity == 'MONTHLY':
                # Move to next month
                if current_date.month == 12:
                    current_date = current_date.replace(year=current_date.year + 1, month=1)
                else:
                    current_date = current_date.replace(month=current_date.month + 1)
        
        total_cost = sum(g['unblended_cost'] for r in results for g in r['groups'])
        total_amortized = sum(g['amortized_cost'] for r in results for g in r['groups'])
        
        return {
            'results_by_time': results,
            'summary': {
                'total_cost': total_cost,
                'total_amortized_cost': total_amortized,
                'currency': 'USD',
                'is_complete': True,
                'regions': self.regions
            },
            'data_type': 'simulated_cost'
        }

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
                            'total_cost': 0, 
                            'total_amortized_cost': 0,
                            'total_usage': 0, 
                            'peak_usage': 0,
                            'regions': set()
                        }
                    }
                
                partitioned_data[service]['time_series'].append({
                    'date': time_result['start_date'],
                    'secondary_dimension': group['secondary_dimension'],
                    'region': group.get('region', 'Unknown'),
                    'unblended_cost': group['unblended_cost'],
                    'amortized_cost': group.get('amortized_cost', 0.0),
                    'usage_quantity': group['usage_quantity'],
                    'usage_unit': group['usage_unit']
                })
                
                partitioned_data[service]['metrics_summary']['total_cost'] += group['unblended_cost']
                partitioned_data[service]['metrics_summary']['total_amortized_cost'] += group.get('amortized_cost', 0.0)
                partitioned_data[service]['metrics_summary']['total_usage'] += group['usage_quantity']
                partitioned_data[service]['metrics_summary']['regions'].add(group.get('region', 'Unknown'))
                partitioned_data[service]['metrics_summary']['peak_usage'] = max(
                    partitioned_data[service]['metrics_summary']['peak_usage'], group['usage_quantity']
                )
        
        # Convert sets to lists for JSON serialization
        for service in partitioned_data:
            partitioned_data[service]['metrics_summary']['regions'] = list(partitioned_data[service]['metrics_summary']['regions'])
            
        return partitioned_data

    def check_cost_increases(self, threshold_settings: Dict = None) -> List[Dict]:
        """Default implementation returns empty list."""
        return []

    def verify_data_completeness(self, processed_data: Dict) -> bool:
        """
        Verifies if the fetched data is complete for the requested period.
        """
        results = processed_data.get('results_by_time', [])
        if not results:
            return False
            
        expected_points = self.analysis_period_days
        if self.granularity == 'WEEKLY':
            expected_points = self.analysis_period_days // 7
        elif self.granularity == 'MONTHLY':
            expected_points = self.analysis_period_days // 30
            
        actual_points = len(results)
        completeness_ratio = actual_points / expected_points if expected_points > 0 else 0
        
        return completeness_ratio >= 0.8


class AWSCostDataExtractor(CostDataSource):
    """ 
    Connects to AWS Cost Explorer, fetches cost and usage data.
    """
    def __init__(self, aws_access_key_id: str, aws_secret_access_key: str, aws_session_token: str = None, region_name: str = 'us-east-1'):
        super().__init__()
        # Handle empty string session token from environment
        if aws_session_token == "":
            aws_session_token = None
            
        self.ce_client = boto3.client(
            'ce',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token,
            region_name=region_name
        )

    def extract_cost_data_by_service_and_usage(self, granularity: str = None) -> Dict:
        """Extract cost data grouped by SERVICE and USAGE_TYPE"""
        if granularity:
            self.granularity = granularity
            
        # AWS doesn't support WEEKLY granularity, so we fetch DAILY and aggregate
        fetch_granularity = self.granularity
        if self.granularity in ['WEEKLY', 'MONTHLY']:
            fetch_granularity = 'DAILY'
            
        try:
            results = []
            next_token = None
            
            while True:
                kwargs = {
                    'TimePeriod': {'Start': self.start_date, 'End': self.end_date},
                    'Granularity': fetch_granularity,
                    'Metrics': ['UnblendedCost', 'AmortizedCost', 'UsageQuantity'],
                    'GroupBy': [
                        {'Type': 'DIMENSION', 'Key': 'SERVICE'},
                        {'Type': 'DIMENSION', 'Key': 'REGION'}
                    ]
                }
                if next_token:
                    kwargs['NextPageToken'] = next_token
                    
                response = self.ce_client.get_cost_and_usage(**kwargs)
                results.extend(response.get('ResultsByTime', []))
                
                next_token = response.get('NextPageToken')
                if not next_token:
                    break
            
            # Construct a combined response object for processing
            combined_response = {'ResultsByTime': results}
            processed = self._process_response(combined_response, 'service_usage')
            
            if self.granularity == 'WEEKLY':
                processed = self._aggregate_to_weekly(processed)
            elif self.granularity == 'MONTHLY':
                processed = self._aggregate_to_monthly(processed)
                
            return processed
        except Exception as e:
            print(f"Error fetching cost data: {e}")
            return {}

    def _aggregate_to_weekly(self, processed_data: Dict) -> Dict:
        """Aggregates daily data into weekly buckets."""
        if not processed_data.get('results_by_time'):
            return processed_data
            
        weekly_results = {} # week_start -> { service_usage -> {cost, usage} }
        
        for result in processed_data['results_by_time']:
            start_date = result['start_date']
            dt = datetime.strptime(start_date, '%Y-%m-%d')
            # Get the start of the week (Monday)
            week_start = (dt - timedelta(days=dt.weekday())).strftime('%Y-%m-%d')
            
            if week_start not in weekly_results:
                weekly_results[week_start] = {}
                
            for group in result['groups']:
                key = (group['service'], group.get('region', 'Unknown'))
                if key not in weekly_results[week_start]:
                    weekly_results[week_start][key] = {
                        'unblended_cost': 0.0,
                        'amortized_cost': 0.0,
                        'usage_quantity': 0.0,
                        'usage_unit': group.get('usage_unit', 'N/A')
                    }
                
                weekly_results[week_start][key]['unblended_cost'] += group['unblended_cost']
                weekly_results[week_start][key]['amortized_cost'] += group.get('amortized_cost', 0.0)
                weekly_results[week_start][key]['usage_quantity'] += group['usage_quantity']
                
        # Reconstruct results_by_time
        new_results = []
        for week_start in sorted(weekly_results.keys()):
            groups = []
            for (service, region), metrics in weekly_results[week_start].items():
                groups.append({
                    'service': service,
                    'secondary_dimension': region,
                    'region': region,
                    'unblended_cost': metrics['unblended_cost'],
                    'amortized_cost': metrics['amortized_cost'],
                    'usage_quantity': metrics['usage_quantity'],
                    'usage_unit': metrics['usage_unit']
                })
            
            new_results.append({
                'start_date': week_start,
                'end_date': (datetime.strptime(week_start, '%Y-%m-%d') + timedelta(days=7)).strftime('%Y-%m-%d'),
                'groups': groups
            })
            
        processed_data['results_by_time'] = new_results
        processed_data['analysis_config']['granularity'] = 'WEEKLY'
        return processed_data

    def _aggregate_to_monthly(self, processed_data: Dict) -> Dict:
        """Aggregates daily data into monthly buckets."""
        if not processed_data.get('results_by_time'):
            return processed_data
            
        monthly_results = {} # month_start -> { service_usage -> {cost, usage} }
        
        for result in processed_data['results_by_time']:
            start_date = result['start_date']
            dt = datetime.strptime(start_date, '%Y-%m-%d')
            # Get the first day of the month
            month_start = dt.replace(day=1).strftime('%Y-%m-%d')
            
            if month_start not in monthly_results:
                monthly_results[month_start] = {}
                
            for group in result['groups']:
                key = (group['service'], group.get('region', 'Unknown'))
                if key not in monthly_results[month_start]:
                    monthly_results[month_start][key] = {
                        'unblended_cost': 0.0,
                        'amortized_cost': 0.0,
                        'usage_quantity': 0.0,
                        'usage_unit': group.get('usage_unit', 'N/A')
                    }
                
                monthly_results[month_start][key]['unblended_cost'] += group['unblended_cost']
                monthly_results[month_start][key]['amortized_cost'] += group.get('amortized_cost', 0.0)
                monthly_results[month_start][key]['usage_quantity'] += group['usage_quantity']
                
        # Reconstruct results_by_time
        new_results = []
        for month_start in sorted(monthly_results.keys()):
            groups = []
            for (service, region), metrics in monthly_results[month_start].items():
                groups.append({
                    'service': service,
                    'secondary_dimension': region,
                    'region': region,
                    'unblended_cost': metrics['unblended_cost'],
                    'amortized_cost': metrics['amortized_cost'],
                    'usage_quantity': metrics['usage_quantity'],
                    'usage_unit': metrics['usage_unit']
                })
            
            # Calculate end of month
            dt = datetime.strptime(month_start, '%Y-%m-%d')
            if dt.month == 12:
                next_month = dt.replace(year=dt.year + 1, month=1)
            else:
                next_month = dt.replace(month=dt.month + 1)
            
            new_results.append({
                'start_date': month_start,
                'end_date': next_month.strftime('%Y-%m-%d'),
                'groups': groups
            })
            
        processed_data['results_by_time'] = new_results
        processed_data['analysis_config']['granularity'] = 'MONTHLY'
        processed_data['analysis_config']['granularity'] = 'MONTHLY'
        return processed_data

    def check_cost_increases(self, threshold_settings: Dict = None) -> List[Dict]:
        """
        Compares costs between the last two available days.
        """
        # Default threshold settings if not provided
        if threshold_settings is None:
            threshold_settings = {
                "threshold_type": "percentage",
                "threshold_value": 10,
                "enabled": True
            }
        
        # If alerts are disabled, return empty list
        if not threshold_settings.get("enabled", True):
            return []
            
        # Fetch last 2 days of data
        end_dt = datetime.now().date()
        start_dt = end_dt - timedelta(days=2)
        
        try:
            response = self.ce_client.get_cost_and_usage(
                TimePeriod={'Start': start_dt.strftime('%Y-%m-%d'), 'End': end_dt.strftime('%Y-%m-%d')},
                Granularity='DAILY',
                Metrics=['UnblendedCost'],
                GroupBy=[{'Type': 'DIMENSION', 'Key': 'SERVICE'}]
            )
            
            results = response.get('ResultsByTime', [])
            if len(results) < 2:
                return []
            
            yesterday_data = results[0].get('Groups', [])
            today_data = results[1].get('Groups', [])
            
            yesterday_costs = {g['Keys'][0]: float(g['Metrics']['UnblendedCost']['Amount']) for g in yesterday_data}
            today_costs = {g['Keys'][0]: float(g['Metrics']['UnblendedCost']['Amount']) for g in today_data}
            
            threshold_type = threshold_settings.get("threshold_type", "percentage")
            threshold_value = float(threshold_settings.get("threshold_value", 10))
            
            alerts = []
            for service, today_cost in today_costs.items():
                yesterday_cost = yesterday_costs.get(service, 0)
                if today_cost > yesterday_cost:
                    increase = today_cost - yesterday_cost
                    percent_increase = ((today_cost - yesterday_cost) / yesterday_cost * 100) if yesterday_cost > 0 else 100
                    
                    # Apply threshold filter
                    should_alert = False
                    if threshold_type == "percentage":
                        should_alert = percent_increase >= threshold_value
                    elif threshold_type == "amount":
                        should_alert = increase >= threshold_value
                    
                    if should_alert:
                        alerts.append({
                            'service': service,
                            'yesterday_cost': yesterday_cost,
                            'today_cost': today_cost,
                            'increase': increase,
                            'percent_increase': percent_increase
                        })
            
            return alerts
        except Exception as e:
            print(f"Error checking cost increases: {e}")
            return []

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
                'total_amortized_cost': 0,
                'total_usage': 0,
                'services': set(),
                'regions': set(),
                'is_complete': True
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
                    'secondary_dimension': group_keys[1] if len(group_keys) > 1 else 'Unknown',
                    'region': group_keys[1] if len(group_keys) > 1 else 'Unknown',
                    'unblended_cost': float(metrics.get('UnblendedCost', {}).get('Amount', 0)),
                    'amortized_cost': float(metrics.get('AmortizedCost', {}).get('Amount', 0)),
                    'usage_quantity': float(metrics.get('UsageQuantity', {}).get('Amount', 0)),
                    'usage_unit': metrics.get('UsageQuantity', {}).get('Unit', 'N/A')
                }
                
                processed_data['summary']['regions'].add(group_data['region'])
                period_data['groups'].append(group_data)
                processed_data['summary']['total_cost'] += group_data['unblended_cost']
                processed_data['summary']['total_amortized_cost'] += group_data['amortized_cost']
                processed_data['summary']['total_usage'] += group_data['usage_quantity']
            
            processed_data['results_by_time'].append(period_data)
        
        processed_data['summary']['services'] = list(processed_data['summary']['services'])
        processed_data['summary']['regions'] = list(processed_data['summary']['regions'])
        
        # Verify completeness
        processed_data['summary']['is_complete'] = self.verify_data_completeness(processed_data)
        
        return processed_data

    def check_cost_increases(self, threshold_settings: Dict = None) -> List[Dict]:
        """
        Compares costs between the last two available days (Simulated).
        """
        # Default threshold settings if not provided
        if threshold_settings is None:
            threshold_settings = {
                "threshold_type": "percentage",
                "threshold_value": 10,
                "enabled": True
            }
        
        # If alerts are disabled, return empty list
        if not threshold_settings.get("enabled", True):
            return []
            
        # Simulate data for last 2 days
        yesterday_costs = {}
        today_costs = {}
        
        for service in self.services:
            base = 50.0 if service == 'AmazonEC2' else 10.0
            yesterday_costs[service] = base * random.uniform(0.9, 1.1)
            # Simulate a spike for one service
            if service == 'AmazonRDS' and random.random() > 0.5:
                today_costs[service] = yesterday_costs[service] * 1.5 # 50% spike
            else:
                today_costs[service] = base * random.uniform(0.9, 1.1)
        
        threshold_type = threshold_settings.get("threshold_type", "percentage")
        threshold_value = float(threshold_settings.get("threshold_value", 10))
        
        alerts = []
        for service, today_cost in today_costs.items():
            yesterday_cost = yesterday_costs.get(service, 0)
            if today_cost > yesterday_cost:
                increase = today_cost - yesterday_cost
                percent_increase = ((today_cost - yesterday_cost) / yesterday_cost * 100) if yesterday_cost > 0 else 100
                
                # Apply threshold filter
                should_alert = False
                if threshold_type == "percentage":
                    should_alert = percent_increase >= threshold_value
                elif threshold_type == "amount":
                    should_alert = increase >= threshold_value
                
                if should_alert:
                    alerts.append({
                        'service': service,
                        'yesterday_cost': yesterday_cost,
                        'today_cost': today_cost,
                        'increase': increase,
                        'percent_increase': percent_increase
                    })
        
        return alerts

class GCPCostDataSource(CostDataSource):
    """
    Simulated GCP Cost Data Source.
    """
    def extract_cost_data_by_service_and_usage(self, granularity: str = None) -> Dict:
        if granularity:
            self.granularity = granularity
            
        # Simulated Data Generation
        services = ['Compute Engine', 'Cloud Storage', 'BigQuery', 'Cloud SQL', 'Cloud Run']
        regions = ['us-central1', 'europe-west1', 'asia-east1']
        
        results = []
        current_date = datetime.strptime(self.start_date, '%Y-%m-%d')
        end_date = datetime.strptime(self.end_date, '%Y-%m-%d')
        
        import random
        random.seed(42) # Consistent simulation
        
        while current_date < end_date:
            next_date = current_date + timedelta(days=1)
            groups = []
            
            for service in services:
                cost = random.uniform(10, 100)
                if service == 'BigQuery': cost *= 2
                
                groups.append({
                    'service': service,
                    'secondary_dimension': random.choice(regions),
                    'region': random.choice(regions),
                    'unblended_cost': cost,
                    'amortized_cost': cost,
                    'usage_quantity': random.uniform(100, 1000),
                    'usage_unit': 'Units'
                })
            
            results.append({
                'start_date': current_date.strftime('%Y-%m-%d'),
                'end_date': next_date.strftime('%Y-%m-%d'),
                'groups': groups
            })
            current_date = next_date
            
        processed_data = {
            'data_type': 'service_usage',
            'analysis_config': {
                'granularity': self.granularity,
                'period_days': self.analysis_period_days,
                'start_date': self.start_date,
                'end_date': self.end_date
            },
            'results_by_time': results,
            'summary': {
                'total_cost': sum(g['unblended_cost'] for r in results for g in r['groups']),
                'total_amortized_cost': sum(g['amortized_cost'] for r in results for g in r['groups']),
                'total_usage': sum(g['usage_quantity'] for r in results for g in r['groups']),
                'services': services,
                'regions': [self.region],
                'is_complete': True
            }
        }
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
                            'total_cost': 0, 
                            'total_amortized_cost': 0,
                            'total_usage': 0, 
                            'peak_usage': 0,
                            'regions': set()
                        }
                    }
                
                partitioned_data[service]['time_series'].append({
                    'date': time_result['start_date'],
                    'secondary_dimension': group['secondary_dimension'],
                    'region': group.get('region', 'Unknown'),
                    'unblended_cost': group['unblended_cost'],
                    'amortized_cost': group.get('amortized_cost', 0.0),
                    'usage_quantity': group['usage_quantity'],
                    'usage_unit': group['usage_unit']
                })
                
                partitioned_data[service]['metrics_summary']['total_cost'] += group['unblended_cost']
                partitioned_data[service]['metrics_summary']['total_amortized_cost'] += group.get('amortized_cost', 0.0)
                partitioned_data[service]['metrics_summary']['total_usage'] += group['usage_quantity']
                partitioned_data[service]['metrics_summary']['regions'].add(group.get('region', 'Unknown'))
                partitioned_data[service]['metrics_summary']['peak_usage'] = max(
                    partitioned_data[service]['metrics_summary']['peak_usage'], group['usage_quantity']
                )
        
        # Convert sets to lists for JSON serialization
        for service in partitioned_data:
            partitioned_data[service]['metrics_summary']['regions'] = list(partitioned_data[service]['metrics_summary']['regions'])
            
        return partitioned_data


from huaweicloudsdkcore.auth.credentials import GlobalCredentials, BasicCredentials
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkbss.v2 import BssClient, ListCustomerselfResourceRecordDetailsRequest, QueryResRecordsDetailReq
from huaweicloudsdkbss.v2.region.bss_region import BssRegion

class HuaweiCostDataSource(CostDataSource):
    """
    Huawei Cloud Cost Data Source using BSS API.
    """
    def __init__(self, ak: str, sk: str, region: str = 'cn-north-1'):
        super().__init__()
        self.ak = ak
        self.sk = sk
        self.region = region
        self.client = self._create_client()

    def _create_client(self):
        print(f"DEBUG: Creating Huawei BSS client for region {self.region}", flush=True)
        # BSS SDK requires GlobalCredentials
        credentials = GlobalCredentials(self.ak, self.sk)
            
        builder = BssClient.new_builder().with_credentials(credentials)
        
        if self.region == 'cn-north-1':
            builder.with_region(BssRegion.value_of(self.region))
        else:
            # For all other regions, use the International endpoint
            endpoint = "https://bss-intl.myhuaweicloud.com"
            print(f"DEBUG: Using international endpoint {endpoint}", flush=True)
            builder.with_endpoint(endpoint)
            
        return builder.build()

    def extract_cost_data_by_service_and_usage(self, granularity: str = None) -> Dict:
        if granularity:
            self.granularity = granularity
            
        # Huawei BSS API typically works with monthly data for detailed records
        # For this implementation, we will fetch data for the requested period
        
        # Convert start/end date to format required by Huawei API (e.g., YYYY-MM) if needed
        # But ListCustomerselfResourceRecordDetailsRequest uses cycle (YYYY-MM)
        
        # We'll iterate through months in the range
        start_dt = datetime.strptime(self.start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(self.end_date, '%Y-%m-%d')
        
        all_records = []
        
        current_month = start_dt.replace(day=1)
        while current_month <= end_dt:
            cycle = current_month.strftime('%Y-%m')
            try:
                self._fetch_month_data(cycle, all_records)
            except Exception as e:
                print(f"Error fetching Huawei cost data for cycle {cycle}: {e}")
            
            # Move to next month
            if current_month.month == 12:
                current_month = current_month.replace(year=current_month.year + 1, month=1)
            else:
                current_month = current_month.replace(month=current_month.month + 1)
                
        processed_data = self._process_records(all_records)
        
        if self.granularity == 'WEEKLY':
            processed_data = self._aggregate_to_weekly(processed_data)
        elif self.granularity == 'MONTHLY':
            processed_data = self._aggregate_to_monthly(processed_data)
            
        return processed_data

    def _fetch_month_data(self, cycle, all_records):
        limit = 100
        offset = 0
        while True:
            # Create the body request object
            query_req = QueryResRecordsDetailReq(
                cycle=cycle,
                limit=limit,
                offset=offset
            )
            
            # Create the main request object and set the body
            request = ListCustomerselfResourceRecordDetailsRequest()
            request.body = query_req
            
            try:
                print(f"DEBUG: Calling Huawei BSS API for cycle {cycle}, offset {offset}", flush=True)
                response = self.client.list_customerself_resource_record_details(request)
            except Exception as e:
                print(f"Error fetching Huawei cost data for cycle {cycle}: {e}", flush=True)
                break
            
            if not response or not response.monthly_records:
                break
                
            print(f"DEBUG: Fetched {len(response.monthly_records)} records", flush=True)
            all_records.extend(response.monthly_records)
            
            if len(response.monthly_records) < limit:
                break
            offset += limit

    def _process_records(self, records) -> Dict:
        # Aggregate by service and region
        # Huawei records have 'cloud_service_type_name', 'region_name', 'official_amount', 'measure_id' (unit)
        
        # We need to map to our daily/weekly structure
        # Note: BSS records might be monthly aggregated or transaction based. 
        # Resource records usually have 'effective_time' or 'bill_date'
        
        results_by_date = {} # date -> { (service, region) -> metrics }
        
        services = set()
        regions = set()
        total_cost = 0.0
        total_usage = 0.0
        
        for record in records:
            # Use bill_date or effective_time. Let's assume bill_date exists or we use cycle start
            # The SDK object structure:
            # record.cloud_service_type_name
            # record.region_name
            # record.official_amount (cost)
            # record.usage_amount
            # record.measure_id (unit)
            # record.bill_date (if available, else use cycle)
            
            service = record.cloud_service_type_name or "Unknown"
            region = record.region_name or "Global"
            # Use consume_amount for exact cost (actual billed amount)
            cost = float(record.consume_amount or record.official_amount or 0.0)
            # usage_amount is not available in MonthlyBillRes, defaulting to 0
            usage = 0.0 
            unit = str(record.measure_id or "Units")
            
            # Try to get date
            date_str = getattr(record, 'bill_date', None)
            if not date_str:
                date_str = getattr(record, 'effective_time', None)
            if not date_str:
                date_str = getattr(record, 'consume_time', None)
            
            # Fallback to trade_id parsing (CSYYMMDD...)
            if not date_str and hasattr(record, 'trade_id') and record.trade_id and record.trade_id.startswith('CS'):
                try:
                    # Extract YYMMDD from CSYYMMDD
                    yymmdd = record.trade_id[2:8]
                    year = 2000 + int(yymmdd[0:2])
                    month = int(yymmdd[2:4])
                    day = int(yymmdd[4:6])
                    date_str = f"{year:04d}-{month:02d}-{day:02d}"
                except:
                    pass
            
            if not date_str:
                date_str = self.start_date
                
            date_str = date_str[:10]
            
            # Filter by date range
            if date_str < self.start_date or date_str > self.end_date:
                continue
                
            services.add(service)
            regions.add(region)
            total_cost += cost
            total_usage += usage
            
            if date_str not in results_by_date:
                results_by_date[date_str] = {}
                
            key = (service, region)
            if key not in results_by_date[date_str]:
                results_by_date[date_str][key] = {
                    'unblended_cost': 0.0,
                    'amortized_cost': 0.0,
                    'usage_quantity': 0.0,
                    'usage_unit': unit
                }
            
            results_by_date[date_str][key]['unblended_cost'] += cost
            results_by_date[date_str][key]['amortized_cost'] += cost # Assuming same for now
            results_by_date[date_str][key]['usage_quantity'] += usage

        # Convert to list format
        results_by_time = []
        for date_str in sorted(results_by_date.keys()):
            groups = []
            for (service, region), metrics in results_by_date[date_str].items():
                groups.append({
                    'service': service,
                    'secondary_dimension': region,
                    'region': region,
                    'unblended_cost': metrics['unblended_cost'],
                    'amortized_cost': metrics['amortized_cost'],
                    'usage_quantity': metrics['usage_quantity'],
                    'usage_unit': metrics['usage_unit']
                })
            
            results_by_time.append({
                'start_date': date_str,
                'end_date': date_str, # Daily
                'groups': groups
            })

        processed_data = {
            'data_type': 'service_usage',
            'analysis_config': {
                'granularity': self.granularity,
                'period_days': self.analysis_period_days,
                'start_date': self.start_date,
                'end_date': self.end_date
            },
            'results_by_time': results_by_time,
            'summary': {
                'total_cost': total_cost,
                'total_amortized_cost': total_cost,
                'total_usage': total_usage,
                'services': list(services),
                'regions': list(regions),
                'is_complete': True
            }
        }
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
                            'total_cost': 0, 
                            'total_amortized_cost': 0,
                            'total_usage': 0, 
                            'peak_usage': 0,
                            'regions': set()
                        }
                    }
                
                partitioned_data[service]['time_series'].append({
                    'date': time_result['start_date'],
                    'secondary_dimension': group['secondary_dimension'],
                    'region': group.get('region', 'Unknown'),
                    'unblended_cost': group['unblended_cost'],
                    'amortized_cost': group.get('amortized_cost', 0.0),
                    'usage_quantity': group['usage_quantity'],
                    'usage_unit': group['usage_unit']
                })
                
                partitioned_data[service]['metrics_summary']['total_cost'] += group['unblended_cost']
                partitioned_data[service]['metrics_summary']['total_amortized_cost'] += group.get('amortized_cost', 0.0)
                partitioned_data[service]['metrics_summary']['total_usage'] += group['usage_quantity']
                partitioned_data[service]['metrics_summary']['regions'].add(group.get('region', 'Unknown'))
                partitioned_data[service]['metrics_summary']['peak_usage'] = max(
                    partitioned_data[service]['metrics_summary']['peak_usage'], group['usage_quantity']
                )
        
        # Convert sets to lists for JSON serialization
        for service in partitioned_data:
            partitioned_data[service]['metrics_summary']['regions'] = list(partitioned_data[service]['metrics_summary']['regions'])
            
        return partitioned_data


import requests

class AWSCostLLMAnalyzer:
    """ 
    Uses a generic AI API (OpenAI-compatible) to analyze partitioned AWS cost data.
    """
    def __init__(self, api_key: str, api_url: str = "https://openrouter.ai/api/v1/chat/completions", model: str = "google/gemini-2.0-flash-exp:free"):
        self.api_key = api_key
        self.api_url = api_url
        self.model = model

    def call_api_with_retry(self, prompt: str, max_retries: int = 3) -> Optional[Dict]:
        """Call the API with exponential backoff for rate limits."""
        
        # Check if we should use direct Gemini SDK
        if self.api_url == "DIRECT_GEMINI":
            return self._call_gemini_direct(prompt, max_retries)

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}]
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://aethercost.ai",
            "X-Title": "AetherCost AI"
        }
        
        base_wait_time = 5
        
        for attempt in range(max_retries + 1):
            try:
                response = requests.post(self.api_url, headers=headers, json=payload, timeout=60)
                
                if response.status_code == 429:
                    wait_time = base_wait_time * (2 ** attempt)
                    print(f"Rate limit hit (429). Retrying in {wait_time}s... (Attempt {attempt + 1}/{max_retries + 1})", flush=True)
                    time.sleep(wait_time)
                    continue
                    
                response.raise_for_status()
                return response.json()
                
            except Exception as e:
                if attempt == max_retries:
                    print(f"API call failed after {max_retries} retries: {e}", flush=True)
                    if 'response' in locals():
                        print(f"Response text: {response.text[:500]}", flush=True)
                    return None
                
                wait_time = base_wait_time * (2 ** attempt)
                print(f"API call failed: {e}. Retrying in {wait_time}s...", flush=True)
                time.sleep(wait_time)
                
        return None

    def _call_gemini_direct(self, prompt: str, max_retries: int = 3) -> Optional[Dict]:
        """Call Google Gemini API directly using the SDK."""
        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(self.model)
        
        base_wait_time = 5
        for attempt in range(max_retries + 1):
            try:
                response = model.generate_content(prompt)
                # Wrap in OpenAI-like format for compatibility with existing parsing logic
                return {
                    "choices": [{
                        "message": {
                            "content": response.text
                        }
                    }]
                }
            except Exception as e:
                if "429" in str(e):
                    wait_time = base_wait_time * (2 ** attempt)
                    print(f"Gemini Rate limit hit. Retrying in {wait_time}s...", flush=True)
                    time.sleep(wait_time)
                    continue
                
                if attempt == max_retries:
                    print(f"Direct Gemini call failed: {e}", flush=True)
                    return None
                
                wait_time = base_wait_time * (2 ** attempt)
                time.sleep(wait_time)
        return None

    def _generate_fallback_analysis(self, service_data: Dict) -> Dict:
        """Generate a basic analysis when API fails."""
        metrics = service_data.get('metrics_summary', {})
        return {
            "service_name": service_data.get('service_name', 'Unknown'),
            "total_cost_analyzed": metrics.get('total_cost', 0),
            "cost_efficiency_score": "N/A",
            "key_findings": [
                "Automated AI analysis unavailable due to API rate limits.",
                f"Total cost for period: ${metrics.get('total_cost', 0):.2f}",
                f"Total usage: {metrics.get('total_usage', 0):.2f}"
            ],
            "optimization_recommendations": [
                {
                    "category": "Manual Review",
                    "description": "Please review AWS Cost Explorer manually for this service.",
                    "estimated_savings": "Unknown",
                    "difficulty": "Medium"
                }
            ],
            "summary_text": f"Basic metrics extracted: Cost=${metrics.get('total_cost', 0):.2f}. Deep analysis failed."
        }

    def analyze_single_service(self, service_data: Dict) -> Dict:
        """Analyze a single service partition."""
        try:
            data_json = json.dumps(service_data, indent=2)
            full_prompt = f"{SERVICE_ANALYSIS_PROMPT}\n\n{data_json}"
            
            system_prompt = "You are a cloud cost optimization expert. Analyze the provided AWS cost data and return a JSON object with your findings."
            result = self.call_api_with_retry(f"{system_prompt}\n\n{full_prompt}")
            if not result:
                print(f"Using fallback analysis for {service_data.get('service_name')}")
                return self._generate_fallback_analysis(service_data)
                
            content = result['choices'][0]['message']['content']
            return json.loads(content, strict=False)
        except Exception as e:
            print(f"Error analyzing service {service_data.get('service_name')}: {e}")
            return self._generate_fallback_analysis(service_data)

    def consolidate_analyses(self, all_analyses: List[Dict]) -> str:
        """Consolidate all individual analyses into a text report."""
        if not all_analyses:
            return "No analyses to consolidate."
        
        analyses_json = json.dumps(all_analyses, indent=2)
        full_prompt = f"{COMBINER_ANALYSIS_PROMPT}\n\n{analyses_json}"
        
        try:
            system_prompt = "You are a cloud cost optimization expert. Consolidate the provided service analyses into a comprehensive markdown report."
            result = self.call_api_with_retry(f"{system_prompt}\n\n{full_prompt}", max_retries=1) 
            if not result:
                raise Exception("API failed")
                
            return result['choices'][0]['message']['content'].strip()
        except Exception as e:
            print(f"Consolidation API failed: {e}. Generating fallback report.")
            # Fallback consolidation
            report = ["# Cost Optimization Report (Fallback)\n"]
            report.append("> **Note:** Detailed AI analysis was limited due to API constraints. Here is a summary of the processed data.\n")
            
            total_cost = sum(a.get('total_cost_analyzed', 0) for a in all_analyses)
            report.append(f"## Total Analyzed Cost: ${total_cost:.2f}\n")
            
            for analysis in all_analyses:
                name = analysis.get('service_name', 'Unknown')
                cost = analysis.get('total_cost_analyzed', 0)
                summary = analysis.get('summary_text', 'No summary available.')
                
                report.append(f"### {name}")
                report.append(f"**Cost:** ${cost:.2f}")
                report.append(f"**Summary:** {summary}\n")
                
                if analysis.get('optimization_recommendations'):
                    report.append("**Recommendations:**")
                    for rec in analysis['optimization_recommendations']:
                        report.append(f"- {rec.get('category')}: {rec.get('description')}")
                report.append("\n---\n")
                
            return "\n".join(report)

    def analyze_batch(self, services_data: List[Dict]) -> Tuple[List[Dict], str]:
        """Analyze multiple services in a single batch request."""
        if not services_data:
            return [], "No services to analyze."
            
        try:
            # Simplify data to reduce token count
            simplified_data = []
            for s in services_data:
                simplified_data.append({
                    "service_name": s.get("service_name"),
                    "metrics_summary": s.get("metrics_summary"),
                    "time_series": s.get("time_series") 
                })
                
            data_json = json.dumps(simplified_data, indent=2)
            full_prompt = f"{BATCH_ANALYSIS_PROMPT}\n\n{data_json}"
            
            system_prompt = "You are a cloud cost optimization expert. Analyze the provided AWS cost data for multiple services."
            print("Sending batch analysis request...", flush=True)
            result = self.call_api_with_retry(f"{system_prompt}\n\n{full_prompt}", max_retries=3)
            
            if not result:
                print("Batch analysis failed. Falling back to individual fallback generation.")
                fallback_analyses = [self._generate_fallback_analysis(s) for s in services_data]
                return fallback_analyses, self.consolidate_analyses(fallback_analyses)
                
            content = result['choices'][0]['message']['content']
            
            # Strip markdown code blocks if present
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            elif content.startswith("```"):
                content = content[3:]
            
            if content.endswith("```"):
                content = content[:-3]
                
            content = content.strip()
            
            parsed = json.loads(content, strict=False)
            batch_analyses = parsed.get('analyses', [])
            consolidated_report = parsed.get('consolidated_report', "No consolidated report generated.")
            
            return batch_analyses, consolidated_report
            
        except Exception as e:
            print(f"Error in batch analysis: {e}")
            if 'content' in locals():
                print(f"Content that failed to parse: {content[:1000]}...")
            fallback_analyses = [self._generate_fallback_analysis(s) for s in services_data]
            return fallback_analyses, self.consolidate_analyses(fallback_analyses)

def prepare_chart_data(partitioned_data: Dict) -> Dict:
    """
    Prepares data for frontend charts.
    """
    if not partitioned_data:
        return {"stacked_bar_data": [], "top_trends": []}

    # 1. Stacked Bar Data (Daily Cost per Service)
    daily_map = {}
    service_totals = {}
    
    for service_name, data in partitioned_data.items():
        total_cost = data.get('metrics_summary', {}).get('total_cost', 0)
        service_totals[service_name] = total_cost
        
        for point in data.get('time_series', []):
            date = point['date']
            cost = float(point['unblended_cost'])
            amortized = float(point.get('amortized_cost', cost))
            
            if date not in daily_map:
                daily_map[date] = {"date": date, "Others": 0.0, "Others_amortized": 0.0}
            
            if service_name not in daily_map[date]:
                daily_map[date][service_name] = 0.0
                daily_map[date][f"{service_name}_amortized"] = 0.0
            
            daily_map[date][service_name] += cost
            daily_map[date][f"{service_name}_amortized"] += amortized

    # Identify Top N services
    top_services = sorted(service_totals.items(), key=lambda x: x[1], reverse=True)[:5]
    top_service_names = {s[0] for s in top_services}

    # Fill missing values and group others
    stacked_bar_data = []
    for date in sorted(daily_map.keys()):
        entry = daily_map[date]
        new_entry = {"date": date, "Others": 0.0, "Others_amortized": 0.0}
        
        for key, val in entry.items():
            if key == "date" or key.endswith("_amortized") or key == "Others":
                continue
                
            service_name = key
            cost = val
            amortized = entry.get(f"{service_name}_amortized", cost)
            
            if service_name in top_service_names:
                new_entry[service_name] = cost
                new_entry[f"{service_name}_amortized"] = amortized
            else:
                new_entry["Others"] += cost
                new_entry["Others_amortized"] += amortized
        
        # Ensure all top services are present
        for top_service in top_service_names:
            if top_service not in new_entry:
                new_entry[top_service] = 0.0
                new_entry[f"{top_service}_amortized"] = 0.0
                
        stacked_bar_data.append(new_entry)

    # 2. Top Trends (Moving Average Trend)
    trends = []
    for service_name, data in partitioned_data.items():
        time_series = sorted(data.get('time_series', []), key=lambda x: x['date'])
        if len(time_series) >= 4:
            # Compare average of first 2 points vs last 2 points for smoother trend
            first_avg = (float(time_series[0]['unblended_cost']) + float(time_series[1]['unblended_cost'])) / 2
            last_avg = (float(time_series[-1]['unblended_cost']) + float(time_series[-2]['unblended_cost'])) / 2
            change = last_avg - first_avg
            
            percent_change = 0.0
            if first_avg > 0:
                percent_change = (change / first_avg) * 100
            
            trends.append({
                "service_name": service_name,
                "change": change,
                "percent_change": percent_change,
                "current_cost": float(time_series[-1]['unblended_cost']),
                "regions": data['metrics_summary'].get('regions', [])
            })
    
    trends.sort(key=lambda x: abs(x['change']), reverse=True)

    return {
        "stacked_bar_data": stacked_bar_data,
        "top_trends": trends[:10]
    }

def analyze_cost_pipeline(aws_access_key: str, aws_secret_key: str, api_key: str, api_url: str, model: str, days: int = 30, target_services: List[str] = None, aws_session_token: str = None, start_date: str = None, end_date: str = None, granularity: str = 'DAILY', account_id: str = None, provider: str = 'aws', region: str = None) -> Tuple[str, Dict, float, Dict]:
    """
    Orchestrates the cost analysis pipeline.
    """
    print(f"Starting Cost Analysis Pipeline ({granularity}) for {provider}...", flush=True)
    
    # 1. Extract Data
    extractor = None
    if provider.lower() == 'gcp':
        extractor = GCPCostDataSource()
    elif provider.lower() == 'huawei':
        extractor = HuaweiCostDataSource(aws_access_key, aws_secret_key, region=region or 'cn-north-1')
    else:
        if os.environ.get('SIMULATE_AWS', 'false').lower() == 'true':
            print("Using Simulated AWS Data Source", flush=True)
            extractor = SimulatedAWSCostDataSource()
        else:
            extractor = AWSCostDataExtractor(aws_access_key, aws_secret_key, aws_session_token, region_name=region or 'us-east-1')
    
    # Set time period for extractor
    if start_date and end_date:
        extractor.set_time_period(start_date=start_date, end_date=end_date)
    else:
        extractor.set_time_period(days_back=days)
    
    raw_data = extractor.extract_cost_data_by_service_and_usage(granularity=granularity)
    if not raw_data:
        return f"Failed to fetch {provider.upper()} cost data. Please check your credentials.", {}, 0.0, {"is_complete": False}
    
    total_account_cost = raw_data.get('summary', {}).get('total_cost', 0.0)
    is_complete = raw_data.get('summary', {}).get('is_complete', False)
        
    partitioned_data = extractor.partition_data_by_service(raw_data)
    
    # 2. Analyze with LLM (Batch)
    analyzer = AWSCostLLMAnalyzer(api_key, api_url, model)
    
    # Smart Service Selection:
    # 1. Always include target services
    # 2. Include any service > 1% of total cost
    # 3. Cap at top 12 services to manage API limits
    services_to_analyze = []
    analyzed_names = set()
    
    sorted_services = sorted(
        partitioned_data.values(), 
        key=lambda x: x['metrics_summary']['total_cost'], 
        reverse=True
    )

    # Priority 1: Target services
    if target_services:
        targets = [t.lower() for t in target_services]
        for service_data in sorted_services:
            s_name = service_data['service_name'].lower()
            if any(t in s_name for t in targets):
                services_to_analyze.append(service_data)
                analyzed_names.add(service_data['service_name'])
    
    # Priority 2: Services > 1% of total cost
    threshold = total_account_cost * 0.01
    for service_data in sorted_services:
        if len(services_to_analyze) >= 12:
            break
        if service_data['service_name'] in analyzed_names:
            continue
            
        if service_data['metrics_summary']['total_cost'] >= threshold:
            services_to_analyze.append(service_data)
            analyzed_names.add(service_data['service_name'])

    # Priority 3: Fill up to top 5 if we have fewer
    for service_data in sorted_services:
        if len(services_to_analyze) >= 5 or len(services_to_analyze) >= 12:
            break
        if service_data['service_name'] not in analyzed_names:
            services_to_analyze.append(service_data)
            analyzed_names.add(service_data['service_name'])
            
    # BATCH ANALYSIS
    print(f"Analyzing {len(services_to_analyze)} services in a single batch...", flush=True)
    all_analyses, final_report = analyzer.analyze_batch(services_to_analyze)
    
    # 4. Prepare Chart Data
    chart_data = prepare_chart_data(partitioned_data)
    
    metadata = {
        "is_complete": is_complete,
        "granularity": granularity,
        "period_days": days,
        "analyzed_services_count": len(all_analyses),
        "total_amortized_cost": raw_data.get('summary', {}).get('total_amortized_cost', 0.0),
        "regions_count": len(raw_data.get('summary', {}).get('regions', []))
    }
    
    return final_report, chart_data, total_account_cost, metadata
