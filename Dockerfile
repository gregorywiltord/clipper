FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y ffmpeg && \
    pip install flask pytube requests && \
    apt-get clean

WORKDIR /app
COPY . .

VOLUME ["/data"]

CMD ["python", "app.py"]
