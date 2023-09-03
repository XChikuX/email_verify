# Use a smaller base image for the build stage
FROM python:3.12.0rc1-alpine as build

# Set working directory
WORKDIR /app

# Copy only the requirements.txt first to leverage Docker cache
COPY requirements.txt .

# Install build dependencies, build the required python packages, and remove build dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Start a new stage to create the final image
FROM python:3.12.0rc1-alpine

# Set working directory
WORKDIR /app

# Copy the Python file
COPY verify.py .

# Copy the Python dependencies installed in the build stage
COPY --from=build /usr/local/lib/python3.12/site-packages/ /usr/local/lib/python3.12/site-packages/

# Set the entrypoint
ENTRYPOINT [ "python3", "-m", "hypercorn", "verify:app", "--bind", "0.0.0.0:8080"]