FROM python:3.10-slim

# Install system dependencies
# tesseract-ocr: for OCR
# libtesseract-dev: development files for tesseract
# poppler-utils: for pdf2image (PDF to image conversion)
# ffmpeg: for audio processing (future proofing)
# curl: for healthchecks
# build-essential: for compiling native extensions
# Install system dependencies
# tesseract-ocr: for OCR (kept for potential image/scanned pdf usage if needed by custom OCR service)
# libtesseract-dev: dev files
# poppler-utils: for pdf2image
# ffmpeg: for audio processing
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    poppler-utils \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first
COPY requirements.txt .

# Install python dependencies with pre-compilation
RUN pip install --no-cache-dir --compile -r requirements.txt

# Copy application code
COPY . .

# Pre-compile all Python files
RUN python -m compileall -q /app/app

# Create necessary directories
RUN mkdir -p /app/uploads /app/logs

# Set environment variables for Python optimization
ENV PYTHONDONTWRITEBYTECODE=0
ENV PYTHONOPTIMIZE=1



# Set environment variables for Python optimization
ENV PYTHONDONTWRITEBYTECODE=0
ENV PYTHONOPTIMIZE=1

# Expose port
EXPOSE 8080

# Health check (adapts to HTTP/HTTPS based on SSL_ENABLED)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD if [ "$SSL_ENABLED" = "True" ] || [ "$SSL_ENABLED" = "true" ]; then \
        curl -fk https://localhost:8080/health; \
    else \
        curl -f http://localhost:8080/health; \
    fi || exit 1

# Run the application (conditionally with or without SSL based on SSL_ENABLED env var)
CMD ["sh", "-c", "if [ \"$SSL_ENABLED\" = \"True\" ] || [ \"$SSL_ENABLED\" = \"true\" ]; then uvicorn app.main:app --host 0.0.0.0 --port 8080 --ssl-keyfile ssl/key.pem --ssl-certfile ssl/cert.pem; else uvicorn app.main:app --host 0.0.0.0 --port 8080; fi"]
