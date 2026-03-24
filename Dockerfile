FROM python:3.13-alpine

# Install system dependencies: Chromium for Selenium
RUN apk add --no-cache \
    chromium \
    chromium-chromedriver

# Workspace config
WORKDIR /app

# Make sure the public directory exists right from the start
RUN mkdir -p public templates

# Install project dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Setup crond schedule
RUN echo "*/15 * * * * cd /app && python /app/scraper.py" > /etc/crontabs/root

# The container will run the initial scrape on startup, then start the cron daemon in the foreground
CMD ["sh", "-c", "python scraper.py && crond -f"]
