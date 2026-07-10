FROM node:20-slim AS web-build
WORKDIR /web
COPY frontend-service/web/package*.json ./
RUN npm install
COPY frontend-service/web ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY frontend-service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY libs ./libs
ENV PYTHONPATH=/app/libs/fastclass-shared
COPY frontend-service/app ./app
COPY --from=web-build /web/dist ./web/dist
RUN mkdir keys
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
