FROM python:3.12-slim
WORKDIR /app
COPY auth-service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY libs ./libs
COPY auth-service/app ./app
COPY auth-service/providers.yaml ./providers.yaml
COPY auth-service/service_clients.yaml ./service_clients.yaml
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
