FROM python:3.12-slim
RUN pip install --no-cache-dir uv
WORKDIR /app
COPY pyproject.toml ./
RUN uv pip install --system --no-cache -e .
COPY . .
ENV PYTHONPATH=/app/src
# ADR 0066 (Priority 1): ran as root before, for no reason -- unlike
# services/api and apps/web, this service has no bind mount (see
# docker-compose.yml: `build: ./apps/signal-bot`, no `volumes:`), so the
# whole image is self-contained and there's no host-file-ownership
# interaction to worry about.
RUN useradd --create-home --uid 1000 appuser && chown -R appuser:appuser /app
USER appuser
CMD ["python", "-m", "signal_bot.main"]
