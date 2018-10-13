FROM python:2
USER root
ADD https://raw.githubusercontent.com/pdxwebdev/yadacoin/master/docker/consensus/entrypoint.sh /entrypoint.sh
#RUN pip install -r https://raw.githubusercontent.com/pdxwebdev/yadacoin/master/requirements.txt
RUN chown myuser:myuser /entrypoint.sh && \
    chmod 744 /entrypoint.sh
USER myuser
ENTRYPOINT [ "/entrypoint.sh" ]
EXPOSE 8000