import os
import sys
# Add current dir to path to import cost_analyzer
sys.path.append('/app')
from cost_analyzer import analyze_cost_pipeline

def reproduce():
    aws_ak = os.getenv('AWS_ACCESS_KEY_ID')
    aws_sk = os.getenv('AWS_SECRET_ACCESS_KEY')
    api_key = os.getenv('GEMINI_API_KEY') or os.getenv('OPENROUTER_API_KEY')
    api_url = os.getenv('AI_API_URL', 'https://openrouter.ai/api/v1')
    model = os.getenv('AI_MODEL', 'google/gemini-2.0-flash-exp:free')
    
    print(f"Reproducing with AK: {aws_ak[:5]}...")
    
    try:
        report, chart, total, meta = analyze_cost_pipeline(
            aws_ak, aws_sk, api_key, api_url, model, days=31, granularity='DAILY'
        )
        print(f"Result Complete: {meta.get('is_complete')}")
        if not meta.get('is_complete'):
            print(f"Report: {report}")
    except Exception as e:
        print(f"Caught Exception: {e}")

if __name__ == "__main__":
    reproduce()
