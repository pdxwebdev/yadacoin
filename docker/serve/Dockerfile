FROM python:2
ADD https://raw.githubusercontent.com/pdxwebdev/yadacoin/master/docker/serve/entrypoint.sh /yadacoin/serve/entrypoint.sh
WORKDIR /yadacoin/serve/
RUN pip install -r https://raw.githubusercontent.com/pdxwebdev/yadacoin/master/requirements.txt
ENTRYPOINT [ "yadacoin/serve/entrypoint.sh" ]
EXPOSE 8000