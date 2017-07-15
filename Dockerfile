FROM python:2.7-onbuild

EXPOSE 10053

COPY server.py requirements.txt

RUN pip install -r requirements.txt; rm requirements.txt

CMD [ "python", "server.py" ]
