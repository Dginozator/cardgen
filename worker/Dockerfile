FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/worker/

# Create fonts directory (fonts mounted or baked in at build time)
RUN mkdir -p /app/worker/fonts

EXPOSE 8766

CMD ["python", "-m", "worker.main"]
