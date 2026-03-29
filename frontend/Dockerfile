FROM node:20-alpine AS base

WORKDIR /app
COPY package.json ./
RUN npm install

COPY . .
RUN npm run build

# standalone モードに必要な静的ファイルをコピー
RUN cp -r .next/static .next/standalone/.next/static
RUN if [ -d public ]; then cp -r public .next/standalone/public; fi

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"
CMD ["node", ".next/standalone/server.js"]
