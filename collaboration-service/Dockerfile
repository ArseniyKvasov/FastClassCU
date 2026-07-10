FROM node:22-slim

WORKDIR /app

COPY collaboration-service/package.json collaboration-service/package-lock.json ./
RUN npm ci

COPY libs/fastclass-node-shared /libs/fastclass-node-shared
COPY collaboration-service/migrations ./migrations
COPY collaboration-service/src ./src
COPY collaboration-service/tsconfig.json ./
COPY collaboration-service/.env.example ./

EXPOSE 8000

CMD ["npm", "start"]
