FROM python:3.11-slim

WORKDIR /app

# Install Python deps first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Expose both API and UI ports
EXPOSE 8000 8501

# Default: start both services via a shell script
CMD ["bash", "start.sh"]
