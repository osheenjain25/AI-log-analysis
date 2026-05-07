FROM python:3.9-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

RUN pip install requests opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp
RUN pip install flask flask-cors boto3 google-generativeai pandas huaweicloudsdkcore huaweicloudsdkbss

COPY datasources.py .
COPY analyzer.py .

CMD ["python", "analyzer.py"]
