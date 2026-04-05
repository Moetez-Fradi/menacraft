FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only PyTorch from official index
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu \
    torch torchvision

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download all model weights BEFORE copying app code.
# This layer is cached independently of code changes — only re-runs
# if requirements.txt or warmup.py itself changes.
COPY warmup.py .
RUN python warmup.py

# Copy the rest of the app code (changes here won't bust the warmup cache)
COPY . .

EXPOSE 8082
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8082", "--workers", "1"]
