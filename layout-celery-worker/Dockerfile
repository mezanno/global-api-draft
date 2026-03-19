FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY celeryconfig.py worker.py /app/

ENV C_FORCE_ROOT=1

CMD ["celery", "--app=worker.celery", "worker", "--loglevel=INFO"]

