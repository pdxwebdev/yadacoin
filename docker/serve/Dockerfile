FROM python:2
WORKDIR /yadacoin/serve/
ADD https://raw.githubusercontent.com/pdxwebdev/yadacoin/master/docker/serve/entrypoint.sh ./
#RUN pip install -r https://raw.githubusercontent.com/pdxwebdev/yadacoin/master/requirements.txt
ENTRYPOINT [ "yadacoin/serve/entrypoint.sh" ]
EXPOSE 8000