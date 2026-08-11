FROM python:3.12-slim@sha256:804ddf3251a60bbf9c92e73b7566c40428d54d0e79d3428194edf40da6521286 AS build
RUN apt-get update \
 && apt-get install -y --no-install-recommends g++ \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY cpp ./cpp
RUN g++ -std=c++17 -O2 -Wall -Wextra -Werror -fPIC -shared cpp/bms_core.cpp -o libbms_core.so \
 && g++ -std=c++17 -O2 -Wall -Wextra -Werror cpp/bms_core.cpp cpp/test_core.cpp -o test_core \
 && ./test_core

FROM python:3.12-slim@sha256:804ddf3251a60bbf9c92e73b7566c40428d54d0e79d3428194edf40da6521286 AS runtime
LABEL org.opencontainers.image.source="https://github.com/ndndndn1/bms-edge-anomaly-runtime"
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    HOME=/nonexistent
RUN groupadd --gid 10001 bms \
 && useradd --uid 10001 --gid 10001 --no-create-home --home-dir /nonexistent \
    --shell /usr/sbin/nologin bms
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --disable-pip-version-check -r requirements.txt
COPY --from=build /build/libbms_core.so /app/libbms_core.so
COPY src ./src
COPY config ./config
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=2)"]
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

FROM runtime AS test
USER root
COPY requirements-dev.txt .
RUN pip install --no-cache-dir --disable-pip-version-check -r requirements-dev.txt
COPY tests ./tests
USER 10001:10001
CMD ["pytest", "-q", "-p", "no:cacheprovider"]
