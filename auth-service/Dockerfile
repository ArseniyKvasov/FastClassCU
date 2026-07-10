FROM python:3.12-slim
WORKDIR /app
COPY auth-service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY libs ./libs
COPY auth-service/alembic ./alembic
COPY auth-service/alembic.ini ./alembic.ini
COPY auth-service/app ./app
COPY auth-service/providers.yaml.example ./providers.yaml
COPY auth-service/service_clients.yaml ./service_clients.yaml
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
