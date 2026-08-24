# Imagen única para los dos procesos del sistema.
#
# Backend (Django/gunicorn) y frontend (NiceGUI) comparten código y
# dependencias, así que comparten imagen: lo que cambia es el comando. Dos
# imágenes casi idénticas costarían el doble de build y de registro sin
# aportar aislamiento real — siguen siendo dos servicios distintos en Compose
# y dos Deployments distintos en Kubernetes, que es donde el aislamiento
# importa.

# ---------------------------------------------------------------- build
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# `requirements.txt` se copia ANTES que el código: mientras las dependencias no
# cambien, Docker reutiliza esta capa aunque el código cambie en cada commit.
COPY requirements.txt ./
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install -r requirements.txt

# ---------------------------------------------------------------- runtime
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings.prod

# `curl` está solo para el HEALTHCHECK. Nada de build-essential ni headers de
# desarrollo: esta etapa solo necesita lo justo para EJECUTAR.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Usuario sin privilegios. El UID fijo es el que exige `runAsNonRoot` en
# Kubernetes (ver deploy/k8s/backend.yaml).
RUN useradd --create-home --shell /bin/bash --uid 10001 arriendos

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=arriendos:arriendos . .

# `datos` guarda la base SQLite; `staticfiles`, lo que recolecte collectstatic.
RUN mkdir -p /app/datos /app/staticfiles \
    && chown -R arriendos:arriendos /app/datos /app/staticfiles

USER arriendos

# 8000 backend · 8080 frontend. Se documentan ambos porque la misma imagen
# sirve para los dos servicios según el comando que reciba.
EXPOSE 8000 8080

# "Sano" aquí es que la API conteste su endpoint de salud, que además
# comprueba la base de datos. El servicio de frontend sobrescribe este
# healthcheck en Compose, porque para él "sano" es otra cosa.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:8000/healthz/ || exit 1

# Sin migraciones en el arranque: con más de una réplica, varios procesos
# migrando a la vez chocan. Las migraciones son un paso propio del despliegue
# (ver el Job de Kubernetes y el stage del Jenkinsfile).
CMD ["gunicorn", "config.wsgi:application", \
     "--chdir", "/app/backend", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--timeout", "60", \
     "--access-logfile", "-"]
