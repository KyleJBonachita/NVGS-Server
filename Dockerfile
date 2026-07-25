FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN groupadd --system nvgs \
    && useradd --system --gid nvgs --home-dir /app nvgs

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x /app/docker/entrypoint.sh \
    && DJANGO_ENVIRONMENT=build DJANGO_SECRET_KEY=build-only-key \
       DATABASE_ENGINE=sqlite python manage.py collectstatic --noinput \
    && chown -R nvgs:nvgs /app

USER nvgs

EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]

