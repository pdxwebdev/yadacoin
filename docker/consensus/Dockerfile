FROM python:2
WORKDIR /usr/src/app
ADD https://raw.githubusercontent.com/pdxwebdev/yadacoin/master/docker/consensus/entrypoint.sh ./
#RUN pip install --no-cache-dir -r https://raw.githubusercontent.com/pdxwebdev/yadacoin/master/requirements.txt
USER root
RUN chmod +x /usr/src/app/entrypoint.sh
ENTRYPOINT [ "/usr/src/app/entrypoint.sh" ]