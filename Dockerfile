FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (layer cached until pyproject.toml changes)
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Copy source after deps (only invalidates this layer on code changes)
COPY src/ src/
COPY config/ config/

# Runtime directories populated via volume mounts — never baked in
RUN mkdir -p runs data/incoming feedback

# Secrets injected at runtime via --env-file or orchestrator env vars
# Never COPY .env or set ENV for secrets here

CMD ["wbsb", "--help"]
