FROM python:3.12-slim
WORKDIR /app
COPY answers-service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY libs ./libs
COPY answers-service/alembic ./alembic
COPY answers-service/alembic.ini ./alembic.ini
COPY answers-service/app ./app
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
