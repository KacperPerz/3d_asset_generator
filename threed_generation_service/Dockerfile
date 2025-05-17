# threed_generation_service/Dockerfile
# This service almost certainly needs a GPU for reasonable performance.
# Using an official PyTorch base image that includes CUDA, cuDNN, and PyTorch.
# Visit https://hub.docker.com/r/pytorch/pytorch/tags to find a suitable tag
# based on the CUDA version your models/host supports and Python version.
# Example: pytorch/pytorch:2.2.1-cuda12.1-cudnn8-runtime

# Using a specific PyTorch version with CUDA 12.1 and Python 3.10 (runtime variant)
FROM python:3.10-slim-bullseye

# The PyTorch images usually come with a pre-installed Python environment.
# They often run as root by default. We will create a non-root user for best practices.

# Set common environment variables (some might be defaults in the base image but explicit is good)
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=UTF-8
ENV DEBIAN_FRONTEND=noninteractive

# Install sudo and procps (for useradd and other utilities if needed), then create a non-root user.
# The pytorch/pytorch images are Ubuntu-based.
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
# The base PyTorch image already has torch. We should ideally manage this by:
# 1. Not listing torch/torchvision/torchaudio in requirements.txt if the base image version is suitable.
# 2. Or, ensuring versions in requirements.txt are compatible or explicitly installing a different version.
# For now, we assume requirements.txt is curated for this base image.
COPY --chown=appuser_3dgen:root requirements.txt .

# Upgrade pip and install dependencies from requirements.txt
# Running pip as the non-root user 'appuser_3dgen'
RUN python3 -m pip install --upgrade pip
RUN python3 -m pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the WORKDIR
COPY --chown=appuser_3dgen:root . .

# Models will be downloaded to /home/appuser_3dgen/.cache/huggingface by default when running as appuser_3dgen
# This path should match the volume mount in docker-compose.yml for caching.

# Expose the port the app runs on
EXPOSE 5002

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5002", "--reload"] 