FROM python:2
WORKDIR /yadacoin/consensus/
ADD https://raw.githubusercontent.com/pdxwebdev/yadacoin/master/docker/consensus/entrypoint.sh /yadacoin
#RUN pip install -r https://raw.githubusercontent.com/pdxwebdev/yadacoin/master/requirements.txt
ENTRYPOINT [ "yadacoin/consensus/entrypoint.sh" ]
EXPOSE 8000