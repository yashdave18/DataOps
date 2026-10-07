FROM apache/airflow:3.3.1-python3.13
WORKDIR /opt/olist
USER root
RUN mkdir -p /opt/olist/data/raw /opt/olist/data/processed \
    && chown -R airflow:root /opt/olist
USER airflow
COPY requirements-runtime.txt ./
# Keep the Airflow version fixed when adding project dependencies.
RUN pip install --no-cache-dir "apache-airflow==3.3.1" -r requirements-runtime.txt
COPY --chown=airflow:root src ./src
COPY --chown=airflow:root sql ./sql
COPY --chown=airflow:root tests ./tests
COPY --chown=airflow:root scripts ./scripts
COPY --chown=airflow:root airflow ./airflow
COPY --chown=airflow:root airflow/dags /opt/airflow/dags
COPY --chown=airflow:root plan.md ./
ENV PYTHONPATH=/opt/olist OLIST_DATA_DIR=/opt/olist/data
