# Use the official Caddy image
FROM caddy:2.9.1

# Copy Caddyfile to the container
COPY Caddyfile /etc/caddy/Caddyfile

# Expose the default Caddy port
EXPOSE 80

# Start the Caddy server
CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
