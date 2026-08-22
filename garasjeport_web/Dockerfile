ARG BUILD_FROM
FROM ${BUILD_FROM}
COPY app.py /app.py
COPY icon-180.png icon-192.png icon-512.png /
COPY run.sh /run.sh
RUN chmod a+x /run.sh
CMD [ "/run.sh" ]
