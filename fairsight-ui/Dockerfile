# Stage 1: Build the React application
FROM node:18-slim AS build
WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm install

# Copy source and build
COPY . .
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# Stage 2: Serve the static files with Nginx
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html

# Custom Nginx config to support React Router (SPA)
# We use '8080' as a placeholder that we will replace at runtime
RUN echo 'server { \
    listen 8080; \
    location / { \
        root /usr/share/nginx/html; \
        index index.html; \
        try_files $uri $uri/ /index.html; \
    } \
}' > /etc/nginx/conf.d/default.conf

# At runtime, replace the placeholder 8080 with the actual $PORT provided by Cloud Run
CMD sh -c "sed -i 's/8080/'${PORT:-8080}'/g' /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"
