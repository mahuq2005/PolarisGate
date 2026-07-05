FROM nginx:1.25-alpine

# Install OpenSSL for self-signed cert generation
RUN apk add --no-cache openssl

# Remove default config
RUN rm /etc/nginx/conf.d/default.conf

# Copy our config
COPY polarisgate.conf /etc/nginx/conf.d/

# Create cert directory
RUN mkdir -p /etc/nginx/certs

# Generate self-signed cert for development
# Production: mount real certs from secrets manager
RUN openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/nginx/certs/polarisgate.key \
    -out /etc/nginx/certs/polarisgate.crt \
    -subj "/C=CA/ST=Ontario/L=Toronto/O=PolarisGate/CN=polarisgate.local"

EXPOSE 80 443

CMD ["nginx", "-g", "daemon off;"]
