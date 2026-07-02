FROM python:3.12-slim
RUN pip install --no-cache-dir uv
WORKDIR /app
COPY pyproject.toml ./
RUN uv pip install --system --no-cache -e .
COPY . .
CMD ["python", "-m", "signal_bot.main"]
