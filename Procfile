release: flask --app server.app db upgrade
web: gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 2
