FROM python:2
ADD https://raw.githubusercontent.com/pdxwebdev/yadacoin/master/docker/mine/entrypoint.sh /yadacoin/mine/entrypoint.sh
WORKDIR /yadacoin/mine/
RUN pip install -r https://raw.githubusercontent.com/pdxwebdev/yadacoin/master/requirements.txt
ENTRYPOINT [ "yadacoin/mine/entrypoint.sh" ]
EXPOSE 8000