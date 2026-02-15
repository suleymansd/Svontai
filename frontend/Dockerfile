FROM node:18-alpine

WORKDIR /app

ENV NODE_ENV=development \
    NEXT_TELEMETRY_DISABLED=1

COPY package.json package-lock.json* ./
RUN npm install

COPY . /app

EXPOSE 3000

CMD ["sh", "-lc", "npm run dev -- -p 3000"]
