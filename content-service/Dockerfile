FROM python:3.12-slim
WORKDIR /app
COPY content-service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY libs ./libs
COPY content-service/app ./app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
