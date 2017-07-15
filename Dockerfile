FROM python:2.7-onbuild

EXPOSE 53

CMD [ "python", "server.py" ]
