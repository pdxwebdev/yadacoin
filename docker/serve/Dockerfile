FROM python:2
ADD . /
WORKDIR /
RUN pip install -r requirements.txt
ENTRYPOINT [ "docker/serve/entrypoint.sh" ]
EXPOSE 8000