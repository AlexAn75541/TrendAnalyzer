FROM python:3.11-slim


WORKDIR /app

# Install CJK fonts to prevent matplotlib rendering errors
RUN apt-get update && apt-get install -y fonts-noto-cjk && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x entrypoint.sh

ENV DATA_DIR=/app/data
EXPOSE 5000

CMD ["./entrypoint.sh"]