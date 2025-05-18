FROM python:3.10-slim-bullseye


ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=UTF-8
ENV DEBIAN_FRONTEND=noninteractive

# Install sudo and procps (for useradd and other utilities if needed), then create a non-root user.
RUN apt-get update && \
    apt-get install -y --no-install-recommends procps sudo git ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN useradd --create-home --uid 1003 --gid 0 appuser_3dgen && \
    echo "appuser_3dgen ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

# Switch to the non-root user
USER appuser_3dgen
WORKDIR /home/appuser_3dgen/app
ENV PATH="/home/appuser_3dgen/.local/bin:${PATH}"

# Copy requirements file first to leverage Docker layer caching.
COPY --chown=appuser_3dgen:root requirements.txt .

# Upgrade pip and install dependencies from requirements.txt
# Running pip as the non-root user 'appuser_3dgen'
RUN python3 -m pip install --upgrade pip
RUN python3 -m pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the WORKDIR
COPY --chown=appuser_3dgen:root . .

EXPOSE 8002

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002", "--reload"] 