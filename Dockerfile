FROM python:3.13-slim

# Install system dependencies: Chromium for Selenium, and cron
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    cron \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Install uv directly from Astral's image for lightning-fast installs
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Workspace config
WORKDIR /app
COPY uv.lock pyproject.toml ./

# Install project dependencies securely to system Python using uv
RUN uv pip install --system selenium beautifulsoup4 jinja2

COPY . .

# Set up cron tab file
# Run the script every 15 minutes, directing output to stdout/stderr so docker logs sees it
RUN echo "*/15 * * * * root cd /app && python scraper.py > /proc/1/fd/1 2>/proc/1/fd/2" > /etc/cron.d/jamix_scrape_cron \
    && chmod 0644 /etc/cron.d/jamix_scrape_cron \
    && crontab /etc/cron.d/jamix_scrape_cron

# Make sure the public directory exists right from the start
RUN mkdir -p public templates

# The container will run the initial scrape on startup, then start the cron daemon in the foreground
CMD ["sh", "-c", "python scraper.py && cron -f"]
