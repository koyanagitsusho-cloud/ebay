FROM node:20-alpine AS base

WORKDIR /app
COPY package.json ./
RUN npm install

COPY . .
RUN npm run build

# next.config.js の output: "standalone" により
# .next/standalone/ に自己完結型サーバーが生成される
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"
CMD ["node", ".next/standalone/server.js"]
