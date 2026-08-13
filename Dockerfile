FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libmagic1 && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md ./
COPY apps ./apps
COPY packages ./packages
COPY frontend ./frontend
COPY db ./db
RUN pip install --no-cache-dir .
EXPOSE 8000
CMD ["uvicorn","apps.api.main:app","--host","0.0.0.0","--port","8000"]
