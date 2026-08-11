FROM python:3.12-slim AS build
RUN apt-get update && apt-get install -y --no-install-recommends g++ && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY cpp ./cpp
RUN g++ -std=c++17 -O2 -Wall -Wextra -Werror -fPIC -shared cpp/bms_core.cpp -o libbms_core.so \
 && g++ -std=c++17 -O2 -Wall -Wextra -Werror cpp/bms_core.cpp cpp/test_core.cpp -o test_core \
 && ./test_core

FROM python:3.12-slim AS runtime
LABEL org.opencontainers.image.source="https://github.com/ndndndn1/bms-edge-anomaly-runtime"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --from=build /build/libbms_core.so /app/libbms_core.so
COPY src ./src
COPY config ./config
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM runtime AS test
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY tests ./tests
CMD ["pytest", "-q"]
