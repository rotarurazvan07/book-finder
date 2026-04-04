# Stage 1: Build
FROM node:22-alpine AS builder

WORKDIR /app

# Copy lockfiles first for caching
COPY frontend/package*.json ./
RUN npm ci

# Copy source (assuming Dockerfile is in repo root)
COPY frontend/ .
RUN npm run build

# Stage 2: Serve
FROM nginx:1.27-alpine

# Use a custom Nginx config for SPA routing (very important for React Router)
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

# Copy build artifacts from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]