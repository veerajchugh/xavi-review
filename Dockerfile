# Portable deploy (Fly.io / Render / Railway). Mount a volume at /data for the sqlite DB.
FROM python:3.12-slim
WORKDIR /app
COPY . /app
ENV DATA_DIR=/data PORT=8080
EXPOSE 8080
CMD ["python3","server.py","--port","8080"]
