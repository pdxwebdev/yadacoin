# syntax=docker/dockerfile:1
# Use an official Python runtime as the base image
FROM python:3.9-slim-bookworm

# Install necessary system packages
RUN apt-get update && \
    apt-get install -y git libssl-dev libffi-dev cmake libjpeg-dev build-essential python3-setuptools \
        autoconf automake libtool pkg-config && \
    apt-get clean

# Set the working directory in the container
WORKDIR /app

# Install the required Python packages
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt --src /usr/local/src

# Copy plugins directory to install plugin-specific requirements
# (app source code is provided at runtime via the volume mount: - .:/app)
COPY plugins/ ./plugins/
RUN --mount=type=cache,target=/root/.cache/pip \
    find plugins -name "requirements.txt" -exec pip install -r {} \;

# Command to run the application
CMD ["python", "yadacoin/app.py", "--config=config/config.json", "--mongohost=mongodb"]