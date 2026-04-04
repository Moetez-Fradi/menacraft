FROM python:3.11-slim
WORKDIR /app

RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu \
    torch==2.3.0+cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download sentence transformer before app code so cache isn't busted by code changes
COPY warmup.py .
RUN python warmup.py

COPY . .

EXPOSE 8083
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8083", "--workers", "1"]
