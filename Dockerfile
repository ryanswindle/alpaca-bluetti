FROM python:3.12-slim

LABEL maintainer="Ryan Swindle <rswindle@gmail.com>"
LABEL description="ASCOM Alpaca server for Bluetti solar generators"

# Install BlueZ and D-Bus for BLE support
RUN apt-get update && apt-get install -y --no-install-recommends \
        bluetooth \
        bluez \
        dbus \
        libdbus-1-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /alpyca

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY config.yaml .
COPY *.py ./

CMD ["python", "main.py"]
