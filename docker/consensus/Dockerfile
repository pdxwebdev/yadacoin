FROM python:2
ADD . /
WORKDIR /
RUN pip install -r https://raw.githubusercontent.com/pdxwebdev/yadacoin/master/requirements.txt
ENTRYPOINT [ "https://raw.githubusercontent.com/pdxwebdev/yadacoin/master/docker/consensus/entrypoint.sh" ]