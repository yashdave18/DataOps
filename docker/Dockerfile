FROM python:3.13-slim-trixie AS app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/opt/olist
WORKDIR /opt/olist
COPY requirements-runtime.txt requirements-analytics.txt requirements-streaming.txt ./
RUN pip install --no-cache-dir -r requirements-runtime.txt -r requirements-analytics.txt -r requirements-streaming.txt
RUN useradd --uid 50000 --gid 0 --create-home olist \
    && mkdir -p /opt/olist/data/raw /opt/olist/data/processed \
    && chown -R 50000:0 /opt/olist
COPY --chown=50000:0 src ./src
COPY --chown=50000:0 sql ./sql
COPY --chown=50000:0 dashboards ./dashboards
COPY --chown=50000:0 kafka ./kafka
COPY --chown=50000:0 spark ./spark
COPY --chown=50000:0 tests ./tests
COPY --chown=50000:0 scripts ./scripts
COPY --chown=50000:0 plan.md README.md ./
USER 50000:0
CMD ["python", "-m", "src.pipeline.runner"]

FROM app AS spark
USER root
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-21-jre-headless \
    && rm -rf /var/lib/apt/lists/*
COPY requirements-spark.txt ./
RUN pip install --no-cache-dir -r requirements-spark.txt
USER 50000:0
CMD ["python", "-m", "spark.transformations"]
