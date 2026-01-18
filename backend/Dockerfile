# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Install system dependencies (Poppler for PDF processing)
RUN apt-get update && apt-get install -y \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend code
COPY . .

# Expose the port the app runs on
EXPOSE 10000

# Run the application
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "10000"]