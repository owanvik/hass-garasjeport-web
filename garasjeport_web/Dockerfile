ARG BUILD_FROM
FROM ${BUILD_FROM}
COPY app.py /app.py
COPY run.sh /run.sh
RUN chmod a+x /run.sh
CMD [ "/run.sh" ]
