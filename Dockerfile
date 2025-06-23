FROM python:3.9-slim
RUN apt-get update 
RUN mkdir -p /app/
WORKDIR /app

COPY /app/* /app/
 
RUN pip install --no-cache-dir -r /app/requirements.txt 
EXPOSE 8000
ENV PYTHONPATH=/app
CMD ["python", "exporter.py"]  