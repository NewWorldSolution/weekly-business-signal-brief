FROM python:3.11-slim

WORKDIR /app

# Copy package descriptor and source, then install
# (editable install requires src/ to exist at install time)
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir -e .

# Config is runtime-only; copy after install so config changes don't bust the pip layer
COPY config/ config/

# Runtime directories populated via volume mounts — never baked in
RUN mkdir -p runs data/incoming feedback

# Secrets injected at runtime via --env-file or orchestrator env vars
# Never COPY .env or set ENV for secrets here

# Run as non-root user (I11-6)
RUN groupadd -r wbsb && useradd -r -g wbsb -u 1000 wbsb
RUN chown -R wbsb:wbsb /app
USER wbsb

CMD ["wbsb", "--help"]
