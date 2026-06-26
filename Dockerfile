FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV WEB_PORT=5173

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5173

CMD ["python", "bot.py"]
