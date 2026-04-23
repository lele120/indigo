# Build stage
FROM node:20-alpine AS build

WORKDIR /app

# Copy package files
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built assets from build stage
COPY --from=build /app/dist /usr/share/nginx/html

# Copy nginx config template. envsubst renders ${MCP_API_KEY} at container
# start so the Bearer token stays out of the image layers and out of the
# JS bundle.
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# Expose port
EXPOSE 80

# nginx:alpine's entrypoint already runs envsubst on /etc/nginx/templates/*
# and writes the result to /etc/nginx/conf.d/, so we just launch nginx.
CMD ["nginx", "-g", "daemon off;"]
