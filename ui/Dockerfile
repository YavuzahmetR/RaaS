# Proof UI — multi-stage: node builds the static bundle, nginx serves it and
# proxies /api/* to the FastAPI service (see nginx.conf; SSE buffering off).

FROM node:22-alpine AS build
WORKDIR /ui
COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /ui/dist /usr/share/nginx/html
EXPOSE 80
