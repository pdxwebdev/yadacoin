FROM python:2
WORKDIR /usr/src/app
ADD https://github.com/pdxwebdev/yadacoin.git ./
RUN pip install --no-cache-dir -r https://raw.githubusercontent.com/pdxwebdev/yadacoin/master/requirements.txt
RUN git clone https://github.com/pdxwebdev/yadacoin.git
RUN chmod +x /usr/src/app/yadacoin/docker/consensus/entrypoint.sh
ENTRYPOINT [ "/usr/src/app/yadacoin/docker/consensus/entrypoint.sh" ]