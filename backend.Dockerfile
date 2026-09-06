FROM python:3.10-slim
WORKDIR /app
RUN apt-get update && apt-get install -y gcc libpq-dev build-essential curl && rm -rf /var/lib/apt/lists/*
COPY requirements/ /app/requirements/
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements/backend.txt
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements/ml.txt
COPY . /app/
EXPOSE 8000
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
