FROM python:2
WORKDIR /yadacoin/mine/
ADD https://raw.githubusercontent.com/pdxwebdev/yadacoin/master/docker/mine/entrypoint.sh .
#RUN pip install -r https://raw.githubusercontent.com/pdxwebdev/yadacoin/master/requirements.txt
ENTRYPOINT [ "yadacoin/mine/entrypoint.sh" ]
EXPOSE 8000