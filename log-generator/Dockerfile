FROM python:3.9-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

COPY main.py .

RUN pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp boto3

CMD ["python", "main.py"]
