FROM node:20-slim AS builder
WORKDIR /app

COPY package*.json ./
COPY tsconfig.* ./
COPY vite.config.ts ./
COPY eslint.config.js ./

RUN npm install

COPY . ./

RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
