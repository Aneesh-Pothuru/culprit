FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CULPRIT_HOST=0.0.0.0 \
    CULPRIT_PORT=8765 \
    CULPRIT_DATABASE=/var/lib/culprit/culprit.sqlite3 \
    CULPRIT_ARTIFACT_DIR=/var/lib/culprit/artifacts

WORKDIR /app
COPY pyproject.toml setup.py README.md LICENSE ./
COPY src ./src
RUN python -m pip install --no-cache-dir --no-build-isolation . \
    && addgroup --system culprit \
    && adduser --system --ingroup culprit culprit \
    && mkdir -p /var/lib/culprit \
    && chown -R culprit:culprit /var/lib/culprit

USER culprit
EXPOSE 8765
VOLUME ["/var/lib/culprit"]
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/readyz', timeout=2).read()"]

CMD ["culprit", "serve"]
