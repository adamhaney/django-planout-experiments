# Dockerfile/nginx/supervisor config inspired by: https://github.com/dockerfiles/django-uwsgi-nginx
FROM python:3.6-slim-stretch

# Native Dependencies
RUN mkdir -p /code

RUN apt-get update && \
    apt-get install -yqq make

# Python Dependencies
ADD requirements.txt /code/requirements.txt
RUN pip install -r /code/requirements.txt

# Our Code
COPY . /code
WORKDIR /code

CMD ["python", "manage.py", "runserver", "0:8000"]
