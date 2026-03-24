FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY ./src /app

EXPOSE 8080

CMD ["uvicorn", "image_to_nsm_service.app:app", "--host", "0.0.0.0", "--port", "8080"]
