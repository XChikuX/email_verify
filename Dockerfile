# Use a smaller base image for the build stage
FROM python:3.12-alpine AS build

# Set working directory
WORKDIR /app

# Install Poetry
RUN pip install --no-cache-dir poetry

# Copy only pyproject.toml and poetry.lock (if present) to leverage Docker cache
COPY pyproject.toml poetry.lock* ./

# Configure Poetry
# Avoid creating a virtual environment inside the Docker container
# and install the dependencies globally in the container
RUN poetry config virtualenvs.create false

# Install dependencies using Poetry
RUN poetry install --no-dev --no-interaction --no-ansi

# Start a new stage to create the final image
FROM python:3.12-alpine

# Set working directory
WORKDIR /trampoline

# Copy the app code
COPY . .

# Copy the installed dependencies from the build stage
COPY --from=build /usr/local/lib/python3.12/site-packages/ /usr/local/lib/python3.12/site-packages/

# Set the entrypoint
ENTRYPOINT ["python3", "-m", "hypercorn", "trampoline:trampoline", "--bind", "0.0.0.0:1234"]