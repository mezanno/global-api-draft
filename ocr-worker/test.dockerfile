FROM python:3.9-slim-bullseye


# Install uv
# ---------------------------------------------------------------------
COPY --from=ghcr.io/astral-sh/uv@sha256:2381d6aa60c326b71fd40023f921a0a3b8f91b14d5db6b90402e65a635053709 /uv /uvx /bin/


# Install project dependencies
# ---------------------------------------------------------------------
# System dependencies

# For OpenCV
RUN --mount=type=cache,target=/var/lib/apt/lists \
    apt-get update && \
    apt-get install -y \
        libgl1 \
        libglib2.0-0
#  --no-install-recommends

# Python dependencies
# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

# Install the project's dependencies using the lockfile and settings
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev



# Install project files
# ---------------------------------------------------------------------
# Then, add the rest of the project source code and install it
# Installing separately from its dependencies allows optimal layer caching
COPY celeryconfig.py pero_ocr_driver.py worker.py /app/
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev


# Finalize installation
# ---------------------------------------------------------------------
# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

# ENV LC_ALL=C
WORKDIR /app

# Declare volumes?
# ---------------------------------------------------------------------
# torch cache and pero models path


# Configure runtime environment
# ---------------------------------------------------------------------
ENV C_FORCE_ROOT=1
# ENV PERO_CONFIG_DIR=/data/pero_ocr/pero_eu_cz_print_newspapers_2020-10-07/

# Wrong CMD?
CMD ["celery", "-A", "worker", "worker", "--loglevel=info" ]
