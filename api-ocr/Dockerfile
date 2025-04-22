FROM python:3.13-slim-bullseye

# Install uv
# ---------------------------------------------------------------------
COPY --from=ghcr.io/astral-sh/uv@sha256:2381d6aa60c326b71fd40023f921a0a3b8f91b14d5db6b90402e65a635053709 /uv /uvx /bin/


# Install project dependencies
# ---------------------------------------------------------------------
# ENV LC_ALL=C
WORKDIR /app

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
COPY celeryconfig.py datatypes.py main_api_ocr.py /app/
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev


# Finalize installation
# ---------------------------------------------------------------------
# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"


# Configure runtime environment
# ---------------------------------------------------------------------
# ENV C_FORCE_ROOT=1
# ENV PERO_CONFIG_DIR=/data/pero_ocr/pero_eu_cz_print_newspapers_2020-10-07/

# Wrong CMD?
CMD ["python", "main_api_ocr.py" ]
