FROM python:3.7
WORKDIR /usr/src/app
ADD https://github.com/pdxwebdev/yadacoin.git ./
RUN pip install --no-cache-dir -r https://raw.githubusercontent.com/pdxwebdev/yadacoin/master/requirements-python3.txt
RUN git clone https://github.com/pdxwebdev/yadacoin.git
RUN chmod +x /usr/src/app/yadacoin/docker/serve/entrypoint.sh
ENTRYPOINT [ "/usr/src/app/yadacoin/docker/serve/entrypoint.sh" ]
EXPOSE 8000