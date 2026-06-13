# Backend: FastAPI + the subprocess sandbox (pandas/matplotlib).
FROM python:3.11-slim

WORKDIR /app

# matplotlib must render headless (no display) inside the container.
ENV MPLBACKEND=Agg \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]
