# ── STAGE 1: BUILD THE REACT APP ─────────────────────────────
FROM node:20-alpine AS build

# Set working directory
WORKDIR /app

# Copy package descriptors first for dependency layer caching
COPY package*.json ./

# Install packages
RUN npm ci --silent

# Copy all source files
COPY . .

# Build the optimized production SPA bundle
RUN npm run build

# ── STAGE 2: PRODUCTION SERVER ────────────────────────────────
FROM nginx:1.25-alpine

# Remove default Nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy custom Nginx proxy server block
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy static build files from build stage to Nginx html directory
COPY --from=build /app/dist /usr/share/nginx/html

# Expose HTTP port 80
EXPOSE 80

# Start Nginx
CMD ["nginx", "-g", "daemon off;"]
