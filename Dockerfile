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

# Plugins ship in the image at /app/plugins, same path existing nodes already use.
# A /plugins volume is optional and must not replace this directory.
COPY . .
RUN mkdir -p /app/plugins && \
    while IFS="$(printf '\t')" read -r name url; do \
      [ -n "${name:-}" ] || continue; \
      case "$name" in \#*) continue ;; esac; \
      case "$url" in \
        git@github.com:*) url="https://github.com/${url#git@github.com:}" ;; \
      esac; \
      git clone --depth 1 "$url" "/app/plugins/$name" || true; \
    done < /app/plugins.txt && \
    for req in /app/plugins/*/requirements.txt; do \
      [ -f "$req" ] || continue; \
      pip install -r "$req"; \
    done

ENTRYPOINT ["sh", "/app/scripts/docker-entrypoint.sh"]
CMD ["python", "yadacoin/app.py", "--config=config/config.json", "--mongohost=mongodb"]