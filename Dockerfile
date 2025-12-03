FROM python:3

RUN apt-get update && apt-get install -y vim less git

# Configure Git to handle line endings properly
RUN git config --global core.autocrlf input
RUN git config --global core.eol lf

ADD . / ./

RUN pip install -r requirements.txt

ENV TERM=xterm

CMD [ "python", "./main.py", "--config-dir", "config", "-e", "TERM=xterm"]
