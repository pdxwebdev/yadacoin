# syntax=docker/dockerfile:1
# Use an official Python runtime as the base image
FROM python:3.9-slim-bookworm

# Install necessary system packages
RUN apt-get update && \
    apt-get install -y git ca-certificates libssl-dev libffi-dev cmake libjpeg-dev build-essential python3-setuptools \
        autoconf automake libtool pkg-config && \
    apt-get clean

# Set the working directory in the container
WORKDIR /app

# Install the required Python packages
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt --src /usr/local/src

# The image is the node. Plugins are mounted at /plugins (or YADA_PLUGINS_DIR).
COPY . .

ENTRYPOINT ["sh", "/app/scripts/docker-entrypoint.sh"]
CMD ["python", "yadacoin/app.py", "--config=config/config.json", "--mongohost=mongodb"]