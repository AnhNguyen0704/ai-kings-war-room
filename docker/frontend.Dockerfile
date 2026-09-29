FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
# SPA fallback + proxy API/WS to backend
RUN printf 'server {\n\
  listen 80;\n\
  root /usr/share/nginx/html;\n\
  location / { try_files $uri $uri/ /index.html; }\n\
  location /api/ { proxy_pass http://backend:8000; }\n\
  location /ws/ { proxy_pass http://backend:8000; proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade"; }\n\
}\n' > /etc/nginx/conf.d/default.conf
EXPOSE 80
