FROM python:3.11-slim
WORKDIR /app

COPY requirements-build.txt .
RUN pip install --no-cache-dir -r requirements-build.txt httpx pytest warp-lang

COPY . .
CMD ["python", "-m", "pytest", "tests/test_deliberate.py", "-q"]
