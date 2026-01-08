# COMBINED_FINOPS_PIPELINE.PY (GRADIO VERSION)

# Standard library imports
import json
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Iterator, Tuple

# Third-party imports
import boto3
import google.generativeai as genai
import pandas as pd
from dotenv import load_dotenv
import gradio as gr

# Local application/library specific imports
# IMPORTANT: This script requires a 'prompts.py' file in the same directory
# with the variables SERVICE_ANALYSIS_PROMPT and COMBINER_ANALYSIS_PROMPT.
from prompts import SERVICE_ANALYSIS_PROMPT, COMBINER_ANALYSIS_PROMPT

# Load environment variables from a .env file
# The `override=True` ensures that any environment variables in the .env file
# will take precedence over system-level environment variables.
load_dotenv(override=True)


# ==============================================================================
# STAGE 1: AWS COST DATA FETCHER
# ==============================================================================

class AWSCostDataExtractor:
    """ 
    Connects to AWS Cost Explorer, fetches cost and usage data based on user input,
    processes it, and partitions it by service for further analysis.
    """
    def __init__(self, aws_access_key_id: Optional[str] = None, 
                 aws_secret_access_key: Optional[str] = None, 
                 region_name: Optional[str] = None):
        """
        Initialize AWS Cost Explorer client.
        Credentials can be passed directly or will be fetched from environment variables.
        """
        # Prioritize passed-in credentials, fall back to environment variables
        self.ce_client = boto3.client(
            'ce',
            aws_access_key_id=aws_access_key_id or os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=aws_secret_access_key or os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=region_name or os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
        )
        
        # These will be set by user input from the Gradio interface
        self.granularity = None
        self.start_date = None
        self.end_date = None
        self.analysis_period_days = None
        self.output_dir = None
        self.base_fetched_data_dir = None
    
    # NOTE: The original get_user_input, _get_specific_dates, and _get_days_back
    # methods are no longer needed as the Gradio UI will handle this.
    # They are kept here for reference but are not called.
    def get_user_input(self):
        """Get granularity and time period from user input"""
        print("🔧 AWS Cost Data Extraction Configuration")
        print("=" * 50)
        
        # Get granularity
        print("\n📊 Choose data granularity:")
        print("1. DAILY - Daily cost breakdown")
        print("2. MONTHLY - Monthly cost breakdown")
        
        while True:
            choice = input("\nEnter your choice (1-2): ").strip()
            if choice == '1':
                self.granularity = 'DAILY'
                break
            elif choice == '2':
                self.granularity = 'MONTHLY'
                break
            else:
                print("❌ Invalid choice. Please enter 1 or 2.")
        
        print(f"✅ Selected granularity: {self.granularity}")
        
        # Get time period
        print("\n📅 Choose time period method:")
        print("1. Enter specific start and end dates")
        print("2. Enter number of days back from today")
        
        while True:
            method = input("\nEnter your choice (1-2): ").strip()
            if method == '1':
                self._get_specific_dates()
                break
            elif method == '2':
                self._get_days_back()
                break
            else:
                print("❌ Invalid choice. Please enter 1 or 2.")
        
        # Calculate analysis period in days
        start_dt = datetime.strptime(self.start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(self.end_date, '%Y-%m-%d')
        self.analysis_period_days = (end_dt - start_dt).days
        
        print(f"✅ Analysis period: {self.start_date} to {self.end_date} ({self.analysis_period_days} days)")
        
        # Create output directory
        self._create_output_directory()
        
        # Display summary
        print(f"\n📋 Configuration Summary:")
        print(f"   📊 Granularity: {self.granularity}")
        print(f"   📅 Start Date: {self.start_date}")
        print(f"   📅 End Date: {self.end_date}")
        print(f"   📊 Period: {self.analysis_period_days} days")
        print(f"   📁 Output Directory: {self.output_dir}")
        
        # Confirm before proceeding
        confirm = input("\nProceed with data extraction? (y/n): ").strip().lower()
        if confirm != 'y':
            print("❌ Extraction cancelled.")
            return False
        
        return True
    
    def _get_specific_dates(self):
        """Get specific start and end dates from user"""
        print("\n📅 Enter dates in YYYY-MM-DD format")
        
        while True:
            start_input = input("Start date: ").strip()
            try:
                datetime.strptime(start_input, '%Y-%m-%d')
                self.start_date = start_input
                break
            except ValueError:
                print("❌ Invalid date format. Please use YYYY-MM-DD (e.g., 2024-01-15)")
        
        while True:
            end_input = input("End date: ").strip()
            try:
                end_dt = datetime.strptime(end_input, '%Y-%m-%d')
                start_dt = datetime.strptime(self.start_date, '%Y-%m-%d')
                
                if end_dt <= start_dt:
                    print("❌ End date must be after start date.")
                    continue
                
                if end_dt > datetime.now():
                    print("❌ End date cannot be in the future.")
                    continue
                
                self.end_date = end_input
                break
            except ValueError:
                print("❌ Invalid date format. Please use YYYY-MM-DD (e.g., 2024-01-15)")
    
    def _get_days_back(self):
        """Get number of days back from today"""
        while True:
            try:
                days_back = int(input("\nEnter number of days back from today: ").strip())
                if days_back <= 0:
                    print("❌ Number of days must be positive.")
                    continue
                
                if days_back > 365:
                    print("⚠️  Warning: Requesting more than 365 days of data.")
                    confirm = input("Continue? (y/n): ").strip().lower()
                    if confirm != 'y':
                        continue
                
                end_date = datetime.now().date()
                start_date = end_date - timedelta(days=days_back)
                
                self.start_date = start_date.strftime('%Y-%m-%d')
                self.end_date = end_date.strftime('%Y-%m-%d')
                break
                
            except ValueError:
                print("❌ Please enter a valid number.")

    def _create_output_directory(self) -> str:
        """Create timestamped output directory inside a 'fetched_data' folder."""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.base_fetched_data_dir = os.path.join(script_dir, 'fetched_data')
        
        if not os.path.exists(self.base_fetched_data_dir):
            os.makedirs(self.base_fetched_data_dir)
            status_message = f"📁 Created base directory for fetched data: {self.base_fetched_data_dir}"
        else:
            status_message = ""

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        granularity_str = self.granularity.lower()
        
        folder_name = f'aws_cost_data_{self.analysis_period_days}days_{granularity_str}_{timestamp}'
        self.output_dir = os.path.join(self.base_fetched_data_dir, folder_name)
        os.makedirs(self.output_dir, exist_ok=True)
        
        status_message += f"\n📁 Output for this run will be saved in: {self.output_dir}"
        return status_message
    
    def get_analysis_description(self):
        """Get formatted description of analysis parameters"""
        return f"{self.analysis_period_days} days ({self.granularity.lower()} granularity)"
    
    def extract_cost_data_by_service_and_usage(self) -> Tuple[Dict, str]:
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
            status_message = "✅ Successfully fetched SERVICE & USAGE_TYPE data."
            return self._process_response(response, 'service_usage'), status_message
        except Exception as e:
            status_message = f"❌ Error fetching SERVICE & USAGE_TYPE data: {str(e)}"
            return {}, status_message
    
    def extract_cost_data_by_service_and_region(self) -> Tuple[Dict, str]:
        """Extract cost data grouped by SERVICE and REGION"""
        try:
            response = self.ce_client.get_cost_and_usage(
                TimePeriod={'Start': self.start_date, 'End': self.end_date},
                Granularity=self.granularity,
                Metrics=['BlendedCost', 'UsageQuantity', 'UnblendedCost'],
                GroupBy=[
                    {'Type': 'DIMENSION', 'Key': 'SERVICE'},
                    {'Type': 'DIMENSION', 'Key': 'REGION'}
                ]
            )
            status_message = "✅ Successfully fetched SERVICE & REGION data."
            return self._process_response(response, 'service_region'), status_message
        except Exception as e:
            status_message = f"❌ Error fetching SERVICE & REGION data: {str(e)}"
            return {}, status_message

    def extract_cost_data_by_service_and_instance_type(self) -> Tuple[Dict, str]:
        """Extract cost data grouped by SERVICE and INSTANCE_TYPE"""
        try:
            response = self.ce_client.get_cost_and_usage(
                TimePeriod={'Start': self.start_date, 'End': self.end_date},
                Granularity=self.granularity,
                Metrics=['BlendedCost', 'UsageQuantity', 'UnblendedCost'],
                GroupBy=[
                    {'Type': 'DIMENSION', 'Key': 'SERVICE'},
                    {'Type': 'DIMENSION', 'Key': 'INSTANCE_TYPE'}
                ],
                Filter={
                    'Dimensions': {
                        'Key': 'SERVICE',
                        'Values': [
                            'Amazon Elastic Compute Cloud - Compute',
                            'Amazon Relational Database Service',
                            'Amazon ElastiCache',
                            'Amazon Elasticsearch Service'
                        ]
                    }
                }
            )
            status_message = "✅ Successfully fetched SERVICE & INSTANCE_TYPE data."
            return self._process_response(response, 'service_instance'), status_message
        except Exception as e:
            status_message = f"❌ Error fetching SERVICE & INSTANCE_TYPE data: {str(e)}"
            return {}, status_message

    def extract_cost_data_by_service_and_tags(self, tag_key: str) -> Tuple[Dict, str]:
        """Extract cost data grouped by SERVICE and a specific TAG"""
        try:
            response = self.ce_client.get_cost_and_usage(
                TimePeriod={'Start': self.start_date, 'End': self.end_date},
                Granularity=self.granularity,
                Metrics=['BlendedCost', 'UsageQuantity', 'UnblendedCost'],
                GroupBy=[
                    {'Type': 'DIMENSION', 'Key': 'SERVICE'},
                    {'Type': 'TAG', 'Key': tag_key}
                ]
            )
            status_message = f"✅ Successfully fetched SERVICE & TAG({tag_key}) data."
            return self._process_response(response, f'service_tag_{tag_key}'), status_message
        except Exception as e:
            status_message = f"❌ Error fetching SERVICE & TAG({tag_key}) data: {str(e)}"
            return {}, status_message
    
    def _process_response(self, response: Dict, data_type: str) -> Dict:
        """Process API response into a structured format."""
        processed_data = {
            'data_type': data_type,
            'analysis_config': {
                'granularity': self.granularity,
                'period_days': self.analysis_period_days,
                'start_date': self.start_date,
                'end_date': self.end_date,
                'description': self.get_analysis_description()
            },
            'group_definitions': response.get('GroupDefinitions', []),
            'results_by_time': [],
            'summary': {
                'total_cost': 0,
                'total_usage': 0,
                'services': set(),
                'time_periods': len(response.get('ResultsByTime', []))
            }
        }
        
        for result in response.get('ResultsByTime', []):
            time_period = result.get('TimePeriod', {})
            period_data = {
                'start_date': time_period.get('Start'),
                'end_date': time_period.get('End'),
                'total_cost': float(result.get('Total', {}).get('BlendedCost', {}).get('Amount', 0)),
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
                    'unblended_cost': float(metrics.get('UnblendedCost', {}).get('Amount', 0)),
                    'usage_quantity': float(metrics.get('UsageQuantity', {}).get('Amount', 0)),
                    'usage_unit': metrics.get('UsageQuantity', {}).get('Unit', 'N/A')
                }
                
                period_data['groups'].append(group_data)
                processed_data['summary']['total_cost'] += group_data['blended_cost']
                processed_data['summary']['total_usage'] += group_data['usage_quantity']
            
            processed_data['results_by_time'].append(period_data)
        
        processed_data['summary']['services'] = list(processed_data['summary']['services'])
        return processed_data
    
    def save_data_to_json(self, data: Dict, filename: str) -> str:
        """Save processed data to a JSON file in the output directory."""
        if data:
            filepath = os.path.join(self.output_dir, filename)
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            return f"💾 Data saved to {filepath}"
        return ""
    
    def get_period_descriptor(self) -> str:
        """Get 'daily' or 'monthly' based on granularity."""
        return self.granularity.lower()
    
    def partition_data_by_service(self, data: Dict) -> Dict:
        """Partition data by service for individual LLM analysis."""
        if not data:
            return {}
        
        partitioned_data = {}
        period_descriptor = self.get_period_descriptor()
        
        for time_result in data.get('results_by_time', []):
            for group in time_result.get('groups', []):
                service = group['service']
                
                if service not in partitioned_data:
                    partitioned_data[service] = {
                        'service_name': service,
                        'data_type': data['data_type'],
                        'analysis_period': f'{self.analysis_period_days}_days_{period_descriptor}',
                        'analysis_config': data['analysis_config'],
                        'time_series': [],
                        'metrics_summary': {
                            'total_cost': 0, 'total_usage': 0, 'avg_period_cost': 0,
                            'peak_usage': 0, 'cost_trend': 'stable'
                        }
                    }
                
                partitioned_data[service]['time_series'].append({
                    'date': time_result['start_date'],
                    'secondary_dimension': group['secondary_dimension'],
                    'blended_cost': group['blended_cost'],
                    'unblended_cost': group['unblended_cost'],
                    'usage_quantity': group['usage_quantity'],
                    'usage_unit': group['usage_unit']
                })
                
                partitioned_data[service]['metrics_summary']['total_cost'] += group['blended_cost']
                partitioned_data[service]['metrics_summary']['total_usage'] += group['usage_quantity']
                partitioned_data[service]['metrics_summary']['peak_usage'] = max(
                    partitioned_data[service]['metrics_summary']['peak_usage'], group['usage_quantity']
                )
        
        for service_data in partitioned_data.values():
            num_time_periods = len(service_data.get('time_series', []))
            if num_time_periods > 0:
                service_data['metrics_summary']['avg_period_cost'] = (
                    service_data['metrics_summary']['total_cost'] / num_time_periods
                )
                if num_time_periods >= 2:
                    costs = [item['blended_cost'] for item in service_data['time_series']]
                    first_half = sum(costs[:len(costs)//2])
                    second_half = sum(costs[len(costs)//2:])
                    if second_half > first_half * 1.1:
                        service_data['metrics_summary']['cost_trend'] = 'increasing'
                    elif second_half < first_half * 0.9:
                        service_data['metrics_summary']['cost_trend'] = 'decreasing'
        
        return partitioned_data

# ==============================================================================
# STAGE 2: GEMINI LLM COST ANALYSER
# ==============================================================================

class AWSCostLLMAnalyzer:
    """ 
    Uses a Generative AI Model (Gemini) to analyze partitioned AWS cost data,
    generate optimization recommendations, and consolidate them into a final report.
    """
    def __init__(self, min_data_points: int, min_cost_threshold: float):
        """Initialize GEMINI client and analysis settings"""
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        
        self.min_data_points = min_data_points
        self.min_cost_threshold = min_cost_threshold
        
        # Ensure the reports directory exists
        self.reports_dir = 'reports'
        os.makedirs(self.reports_dir, exist_ok=True)
        
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    def should_analyze_file(self, file_path: str) -> Tuple[bool, str]:
        """Check if a file meets the criteria for analysis (data points and cost)."""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            time_series_count = len(data.get('time_series', []))
            if time_series_count < self.min_data_points:
                return False, f"Insufficient data points: {time_series_count} < {self.min_data_points}"
            
            total_cost = data.get('metrics_summary', {}).get('total_cost', 0)
            if total_cost < self.min_cost_threshold:
                return False, f"Cost below threshold: ${total_cost:.2f} < ${self.min_cost_threshold:.2f}"
            
            return True, "Meets analysis criteria"
        except Exception as e:
            return False, f"Error reading file: {str(e)}"
    
    def analyze_single_service(self, file_path: str) -> Tuple[Dict, str]:
        """Analyze a single service partition file with GEMINI."""
        status_log = []
        try:
            with open(file_path, 'r') as f:
                service_data = json.load(f)
            
            data_json = json.dumps(service_data, indent=2)
            full_prompt = f"{SERVICE_ANALYSIS_PROMPT}\n\n{data_json}"
            
            status_log.append(f"   🤖 Analyzing {service_data.get('service_name', 'Unknown')} ({service_data.get('data_type', 'Unknown')})...")
            
            response = self.model.generate_content(full_prompt)
            
            try:
                response_text = response.text
                if "```json" in response_text:
                    json_start = response_text.find("```json") + 7
                    json_end = response_text.rfind("```")
                    response_text = response_text[json_start:json_end]
                
                analysis_result = json.loads(response_text)
                analysis_result['analysis_timestamp'] = datetime.now().isoformat()
                analysis_result['source_file'] = os.path.basename(file_path)
                return analysis_result, "\n".join(status_log)
                
            except json.JSONDecodeError as e:
                status_log.append(f"   ⚠️  JSON parsing error for {os.path.basename(file_path)}: {e}")
                return {
                    "service_name": service_data.get('service_name', 'Unknown'),
                    "analysis_error": "JSON parsing failed",
                    "raw_response": response.text,
                    "source_file": os.path.basename(file_path)
                }, "\n".join(status_log)
            
        except Exception as e:
            status_log.append(f"   ❌ Error analyzing {file_path}: {str(e)}")
            return {}, "\n".join(status_log)
    
    def analyze_all_partitions(self, partitions_dir: str) -> Iterator[str | List[Dict]]:
        """Analyze all partition files in a directory that meet the criteria."""
        if not os.path.exists(partitions_dir):
            yield f"❌ Partitions directory not found: {partitions_dir}"
            yield []
            return
        
        yield f"🔍 Scanning partition files in: {partitions_dir}"
        partition_files = [f for f in os.listdir(partitions_dir) if f.endswith('.json')]
        yield f"📄 Found {len(partition_files)} partition files"
        
        eligible_files = []
        for file_name in partition_files:
            file_path = os.path.join(partitions_dir, file_name)
            should_analyze, reason = self.should_analyze_file(file_path)
            if should_analyze:
                eligible_files.append(file_path)
            else:
                yield f"   ⏭️  Skipped {file_name}: {reason}"
        
        yield f"✅ {len(eligible_files)} files eligible for analysis"
        
        all_analyses = []
        for i, file_path in enumerate(eligible_files, 1):
            yield f"\n🔬 [{i}/{len(eligible_files)}] Analyzing: {os.path.basename(file_path)}"
            analysis, status_msg = self.analyze_single_service(file_path)
            yield status_msg
            if analysis:
                all_analyses.append(analysis)
                yield f"   ✅ Analysis completed for: {analysis.get('service_name', 'Unknown')}"
            time.sleep(1)  # Rate limiting
        
        yield all_analyses
    
    def consolidate_analyses(self, all_analyses: List[Dict]) -> Tuple[str, str]:
        """Use a combiner prompt to consolidate all individual analyses into a text report."""
        if not all_analyses:
            return "Error: No analyses to consolidate.", "Error: No analyses to consolidate."
        
        status_message = f"\n🔄 Consolidating {len(all_analyses)} individual analyses..."
        analyses_json = json.dumps(all_analyses, indent=2)
        full_prompt = f"{COMBINER_ANALYSIS_PROMPT}\n\n{analyses_json}"
        
        try:
            response = self.model.generate_content(full_prompt)
            # Gradio markdown sometimes has issues with ```, so we strip them.
            consolidated_report = response.text.replace("```markdown", "").replace("```", "").strip()
            return consolidated_report, status_message
        except Exception as e:
            error_message = f"❌ Error in consolidation: {str(e)}"
            return error_message, error_message
    
    ### MODIFICATION 1: Changed method to return the report path ###
    def generate_final_report(self, consolidated_report: str, all_analyses: List[Dict]) -> Tuple[str, str, str]:
        """
        Generate the final comprehensive report as a text file and return its path.
        Returns:
            Tuple[str, str, str]: The report text, a status message, and the report file path.
        """
        status_message = "\n📊 Generating final cost optimization report..."
        
        report_header = f"""
========================================
AWS COST OPTIMIZATION ANALYSIS REPORT
========================================
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
========================================
"""
        final_report_text = report_header + consolidated_report
        
        report_footer = "\n\n========================================\nANALYSIS METADATA\n========================================\nIndividual Services Analyzed:\n"
        for analysis in all_analyses:
            service_name = analysis.get('service_name', 'Unknown')
            source_file = analysis.get('source_file', 'N/A')
            error = analysis.get('analysis_error')
            if error:
                report_footer += f"• {service_name} ({source_file}) - ERROR: {error}\n"
            else:
                cost = analysis.get('total_cost_analyzed', 0)
                efficiency = analysis.get('cost_efficiency_score', 'N/A')
                report_footer += f"• {service_name} ({source_file}): ${cost:.2f} - Grade: {efficiency}\n"
        
        final_report_text += report_footer
        
        report_filename = f'aws_cost_optimization_report_{self.timestamp}.txt'
        report_path = os.path.join(self.reports_dir, report_filename)
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(final_report_text)
        
        status_message += f"\n✅ Final report saved to: {report_path}"
        return final_report_text, status_message, report_path

# ==============================================================================
# MAIN EXECUTION ORCHESTRATOR
# ==============================================================================
# NOTE: The original `main` function is kept for reference but is not used by Gradio.
def main():
    """Main function to run the complete FinOps pipeline."""
    print("🚀 STARTING AUTOMATED AWS FINOPS PIPELINE 🚀")
    print("=" * 60)

    # --- STAGE 1: DATA FETCHING AND PARTITIONING ---
    print("\n--- STAGE 1: Data Extraction & Partitioning ---")
    extractor = AWSCostDataExtractor()
    if not extractor.get_user_input():
        print("\n❌ Data extraction cancelled. Exiting pipeline.")
        return

    print(f"\n🚀 Starting AWS Cost Data Extraction ({extractor.get_analysis_description()})...")
    
    # Extract different views of the cost data
    service_usage_data, status = extractor.extract_cost_data_by_service_and_usage()
    print(status)
    print(extractor.save_data_to_json(service_usage_data, 'raw_service_usage_data.json'))
    
    service_region_data, status = extractor.extract_cost_data_by_service_and_region()
    print(status)
    print(extractor.save_data_to_json(service_region_data, 'raw_service_region_data.json'))
    
    service_instance_data, status = extractor.extract_cost_data_by_service_and_instance_type()
    print(status)
    print(extractor.save_data_to_json(service_instance_data, 'raw_service_instance_data.json'))
    
    tag_key = 'Environment'
    service_tag_data, status = extractor.extract_cost_data_by_service_and_tags(tag_key)
    print(status)
    print(extractor.save_data_to_json(service_tag_data, f'raw_service_tag_{tag_key}.json'))
    
    # Create partitions directory and process the data
    partitions_dir = os.path.join(extractor.output_dir, 'partitions')
    os.makedirs(partitions_dir, exist_ok=True)
    print(f"\n📁 Created partitions directory: {partitions_dir}")
    
    print("\nPartitioning data by service for LLM analysis...")
    data_sources = [
        (service_usage_data, 'usage'), (service_region_data, 'region'),
        (service_instance_data, 'instance'), (service_tag_data, 'tag')
    ]
    
    for data, data_type in data_sources:
        if data:
            partitioned_data = extractor.partition_data_by_service(data)
            for service, service_data in partitioned_data.items():
                safe_service_name = service.replace(' ', '_').replace('-', '_').lower()
                filename = f'{safe_service_name}_{data_type}_partition.json'
                filepath = os.path.join(partitions_dir, filename)
                with open(filepath, 'w') as f:
                    json.dump(service_data, f, indent=2, default=str)
                print(f"   📄 Created partition: {filename}")
                
    print(f"\n✅ STAGE 1 COMPLETE: Data partitioned and saved to '{partitions_dir}'")
    print("=" * 60)

    # --- STAGE 2: LLM ANALYSIS AND REPORTING ---
    # This section is for reference and would need parameters and generator handling.
    print("\n--- STAGE 2: LLM Analysis & Reporting ---")
    # analyzer = AWSCostLLMAnalyzer(min_data_points=5, min_cost_threshold=10.0)
    
    # # Step 1: Analyze all individual partitions (requires handling the generator)
    # analysis_generator = analyzer.analyze_all_partitions(partitions_dir)
    # all_analyses = []
    # for item in analysis_generator:
    #     if isinstance(item, str):
    #         print(item)
    #     elif isinstance(item, list):
    #         all_analyses = item
    
    # if not all_analyses:
    #     print("\n❌ No eligible services for analysis or all analyses failed. Exiting pipeline.")
    #     return

    # # Step 2: Consolidate analyses
    # consolidated_report, status = analyzer.consolidate_analyses(all_analyses)
    # print(status)
    
    # # Step 3: Generate final report
    # final_report, status = analyzer.generate_final_report(consolidated_report, all_analyses)
    # print(status)
    # print(f"\nFinal report content:\n{final_report}")

    print("\n✅ STAGE 2 COMPLETE: Analysis report generated.")
    print("=" * 60)
    print("🎉 FINOPS PIPELINE COMPLETED SUCCESSFULLY! 🎉")

