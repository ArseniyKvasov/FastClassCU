FROM node:22-slim

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY migrations ./migrations
COPY src ./src
COPY tsconfig.json ./
COPY .env.example ./

EXPOSE 8000

CMD ["npm", "start"]
