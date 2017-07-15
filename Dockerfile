FROM python:2.7-onbuild

EXPOSE 53

ENV HTTP_PROXY ''
ENV HTTPS_PROXY ''

COPY server.py requirements.txt .

RUN pip install -r requirements.txt; rm requirements.txt

CMD [ "python", "server.py" ]
