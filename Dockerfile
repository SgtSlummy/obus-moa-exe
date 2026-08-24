FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir uvicorn fastapi httpx pytest
CMD ["pytest", "tests/test_deliberate.py", "-q"]
