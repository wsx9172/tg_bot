FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /opt/tg_bot

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /opt/tg_bot/messages
RUN chmod +x /opt/tg_bot/entrypoint.sh

EXPOSE 33333

ENTRYPOINT ["/opt/tg_bot/entrypoint.sh"]
CMD ["python", "main.py"]
