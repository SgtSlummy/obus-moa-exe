FROM python:3.11-slim
WORKDIR /app

COPY requirements-build.txt .
COPY requirements-warp.txt .
RUN pip install --no-cache-dir -r requirements-build.txt -r requirements-warp.txt httpx pytest

COPY . .
CMD ["python", "-m", "pytest", "tests/test_deliberate.py", "-q"]
