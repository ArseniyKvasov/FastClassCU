FROM python:3.12-slim
WORKDIR /app
COPY analytics-service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY libs ./libs
COPY analytics-service/alembic ./alembic
COPY analytics-service/alembic.ini ./alembic.ini
COPY analytics-service/pytest.ini ./pytest.ini
COPY analytics-service/app ./app
COPY analytics-service/tests ./tests
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
