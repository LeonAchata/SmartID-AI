
FROM python:3.11-slim as builder

# Metadatos
LABEL maintainer="Leon"
LABEL description="Pipeline de extracción de datos de documentos de identidad"

# Variables de entorno para Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Instalar dependencias del sistema necesarias para PyMuPDF y compilación
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Build essentials
    gcc \
    g++ \
    make \
    # PyMuPDF dependencies
    libfreetype6-dev \
    libjpeg-dev \
    libpng-dev \
    libopenjp2-7-dev \
    # Cleanup
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de trabajo
WORKDIR /app

# Copiar requirements y instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ======================================
# STAGE 2: Runtime
# ======================================
FROM python:3.11-slim

# Variables de entorno
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Instalar solo las dependencias runtime necesarias (sin build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Runtime libraries para PyMuPDF
    libfreetype6 \
    libjpeg62-turbo \
    libpng16-16 \
    libopenjp2-7 \
    # Utilities
    curl \
    # Cleanup
    && rm -rf /var/lib/apt/lists/*

# Crear usuario no-root por seguridad
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app /app/temp && \
    chown -R appuser:appuser /app

# Cambiar a usuario no-root
USER appuser

# Establecer directorio de trabajo
WORKDIR /app

# Copiar dependencias de Python desde builder
COPY --from=builder --chown=appuser:appuser /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder --chown=appuser:appuser /usr/local/bin /usr/local/bin

# Copiar código de la aplicación
COPY --chown=appuser:appuser . .

# Asegurar que el directorio temp existe y tiene permisos
RUN mkdir -p temp && chmod 755 temp

# Exponer puerto (Railway usa variable PORT)
EXPOSE ${PORT}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Copiar entrypoint y darle permisos
COPY --chown=appuser:appuser entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]