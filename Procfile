web: gunicorn movie_management.wsgi:application
worker: celery -A movie_management worker --loglevel=info
