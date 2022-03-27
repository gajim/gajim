FROM python:3.9

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    apt-utils \
    appstream-util \
    libgirepository1.0-dev \
    gir1.2-gtk-3.0 \
    gir1.2-soup-2.4 \
    gir1.2-ayatanaappindicator3-0.1 \
    gettext \
    nodejs \
    npm \
  && adduser --disabled-password worker

WORKDIR /home/worker
ENV PATH="/home/worker/.local/bin:${PATH}"
USER worker

COPY --chown=worker:worker requirements.txt requirements.txt
RUN pip install --upgrade pip && pip install --no-cache-dir --user -r requirements.txt

CMD bash
