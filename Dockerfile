FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install chromium

COPY . .

ENV PORT=8080

CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
