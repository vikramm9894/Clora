# Multi-stage production build for CLORA Sovereign Frontend
FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# Production static serving container
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html

# Expose standard frontend port
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
