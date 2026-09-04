FROM python:3.10-slim
WORKDIR /app
RUN apt-get update && apt-get install -y gcc libpq-dev build-essential
COPY requirements/ /app/requirements/
RUN pip install --no-cache-dir -r requirements/backend.txt
RUN pip install --no-cache-dir -r requirements/ml.txt
COPY . /app/
