FROM python:3.10-slim
WORKDIR /app
RUN apt-get update && apt-get install -y gcc libpq-dev build-essential
COPY requirements/ /app/requirements/
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements/backend.txt
RUN pip install --no-cache-dir --default-timeout=3000 --retries 15 torch torchvision
RUN pip install --no-cache-dir -r requirements/ml.txt
COPY . /app/
