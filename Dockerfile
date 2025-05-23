FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the dependencies file to the working directory
COPY requirements.txt .

# Install any needed dependencies specified in requirements.txt
# --no-cache-dir reduces image size
RUN pip install --no-cache-dir -r requirements.txt

# Copy the content of the local src directory to the working directory
COPY . .

# Make port 8000 available to the world outside this container
# (FastAPI default is 8000, uvicorn in main.py also uses 8000 for local dev)
EXPOSE 8000

# Define the command to run the application
# It will be accessible on port 8000 inside the container.
# 0.0.0.0 binds to all available network interfaces.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
