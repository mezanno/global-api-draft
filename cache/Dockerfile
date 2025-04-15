FROM nginx:1.27.4-alpine

# Copy the "default" configuration file
COPY ./default.conf /etc/nginx/conf.d/default.conf

# Create a volume for the cache
VOLUME /var/cache/nginx

# Keep default CMD from base image (start nginx)
