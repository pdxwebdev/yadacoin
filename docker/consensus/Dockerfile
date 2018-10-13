FROM python:2
ADD https://raw.githubusercontent.com/pdxwebdev/yadacoin/master/docker/consensus/entrypoint.sh /yadacoin/consensus/entrypoint.sh
WORKDIR /yadacoin/consensus/
RUN pip install -r https://raw.githubusercontent.com/pdxwebdev/yadacoin/master/requirements.txt
ENTRYPOINT [ "yadacoin/consensus/entrypoint.sh" ]
EXPOSE 8000