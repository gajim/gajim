FROM python:3.7

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update
RUN apt-get install -y apt-utils
RUN apt-get install -y appstream-util
RUN apt-get install -y libgirepository1.0-dev
RUN apt-get install -y gir1.2-gtk-3.0
RUN apt-get install -y gir1.2-soup-2.4
RUN apt-get install -y gettext

RUN adduser --disabled-password worker
WORKDIR /home/worker
ENV PATH="/home/worker/.local/bin:${PATH}"
USER worker

RUN pip install --upgrade pip

COPY --chown=worker:worker requirements.txt requirements.txt
RUN pip install --no-cache-dir --user -r requirements.txt

CMD bash
