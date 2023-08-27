# Use an official Python runtime as the base image
FROM python:3.9-slim

# Install Git
RUN apt-get update && \
    apt-get install -y git libssl-dev cmake libjpeg-dev build-essential && \
    apt-get clean

# Set the working directory in the container
WORKDIR /app

# Copy the entire directory into the container
COPY . .
# new comment
# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Specify that we are working in the yadacoin subdirectory for the CMD
CMD ["python", "yadacoin/app.py"]
