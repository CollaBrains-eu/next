FROM python:3.12-slim
RUN pip install --no-cache-dir uv
WORKDIR /app
COPY pyproject.toml ./
RUN uv pip install --system --no-cache -e .
COPY . .
# ADR 0066 (Priority 1): ran as root before, for no reason the app needs --
# it never writes anything under /app at runtime (uploads stream straight to
# Paperless over HTTP, no local temp files), so a non-root user costs
# nothing here. --reload is kept: this service's only deploy path bind-mounts
# ./services/api over /app (see docker-compose.yml) specifically so live
# edits take effect without a rebuild, an established workflow this change
# doesn't touch. `chown` matters mainly for anyone building/running this
# image without that bind mount (e.g. CI); the bind mount overrides it in
# the actual deployment, where real read access instead depends on the host
# files being world-readable, as a normal `git clone` produces.
RUN useradd --create-home --uid 1000 appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000

# --no-access-log (ADR 0066 Priority 2, item 3): the request-logging
# middleware in api/main.py now emits one structured JSON line per request
# (method, path, status, duration_ms, request_id) -- uvicorn's own plaintext
# access log would just duplicate that in a second, unparsable format.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--app-dir", "src", "--no-access-log"]
