FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home campus
COPY server ./server
COPY migrations ./migrations
COPY templates ./templates
COPY static ./static
COPY wsgi.py gunicorn.conf.py ./
USER campus
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=8s --start-period=20s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/ready',timeout=6)"
CMD ["gunicorn", "--config", "gunicorn.conf.py", "wsgi:app"]
