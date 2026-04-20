FROM python:3.12-slim-bookworm

WORKDIR /app

# System deps (rtree, shapely wheels generally include GEOS, but rtree needs libspatialindex)
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    libspatialindex6 \
  && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/

ENV PYTHONPATH=/app/backend
EXPOSE 8081

CMD ["uvicorn", "metacam.main:app", "--host", "0.0.0.0", "--port", "8081"]
