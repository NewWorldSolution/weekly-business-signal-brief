FROM python:3.11-slim AS builder

WORKDIR /build

COPY pyproject.toml requirements.lock ./
COPY src/ ./src/
RUN pip install --no-cache-dir -r requirements.lock
RUN pip install --no-cache-dir .

FROM python:3.11-slim AS production

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY src/ ./src/
COPY config/ ./config/

# Runtime directories populated via volume mounts — never baked in
RUN mkdir -p /app/runs /app/data/incoming /app/feedback

# Secrets injected at runtime via --env-file or orchestrator env vars
# Never COPY .env or set ENV for secrets here

# Run as non-root user (I11-6)
RUN groupadd -r wbsb && useradd -r -g wbsb -u 1000 wbsb
RUN chown -R wbsb:wbsb /app
USER wbsb

CMD ["wbsb", "--help"]
