FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home appuser
COPY app/ app/

# Test image: adds test dependencies, the tests and the sample config.
FROM base AS test
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY tests/ tests/
COPY config.xml .
USER appuser
ENTRYPOINT ["python", "-m", "pytest", "-p", "no:cacheprovider"]

# Runtime image (the default): only the app and its two libraries.
FROM base AS app
USER appuser
ENTRYPOINT ["python", "-m", "app.main"]
