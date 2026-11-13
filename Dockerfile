# Render (runtime: docker). Storage = Render Postgres via DATABASE_URL; secrets via env vars.
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app
ENV PORT=8080 DATA_DIR=/tmp/xavi-data PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["python3","server.py"]
