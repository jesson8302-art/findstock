FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

EXPOSE 8000

CMD ["python", "-c", "import os,uvicorn; uvicorn.run('app:app', host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))"]
