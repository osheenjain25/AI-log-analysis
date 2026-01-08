# Stage 1: Build Frontend
FROM node:18-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install --legacy-peer-deps
COPY frontend/ ./
RUN npm run build

# Stage 2: Backend and Serving
FROM python:3.9-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
RUN pip install fastapi uvicorn requests pydantic "python-jose[cryptography]" "passlib[argon2]" python-multipart boto3
COPY main.py .
COPY --from=frontend-builder /app/frontend/dist ./static
EXPOSE 8080
CMD ["python", "main.py"]
