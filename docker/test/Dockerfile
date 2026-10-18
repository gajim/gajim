FROM debian:unstable-slim

COPY requirements.txt requirements.txt
RUN apt-get update
RUN apt-get install -y \
    apt-utils \
    appstream \
    gettext \
    nodejs \
    npm \
    python-is-python3 \
    python3-build \
    python3-cryptography \
    python3-css-parser \
    python3-full \
    python3-gi \
    python3-gssapi \
    python3-idna \
    python3-packaging \
    python3-pil \
    python3-pip \
    python3-precis-i18n \
    python3-protobuf \
    python3-qrcode \
    python3-sentry-sdk \
    python3-setuptools \
    gir1.2-adw-1 \
    gir1.2-geoclue-2.0 \
    gir1.2-gst-plugins-base-1.0 \
    gir1.2-gstreamer-1.0 \
    gir1.2-gtk-4.0 \
    gir1.2-gtksource-5 \
    gir1.2-soup-3.0

# pycairo build deps
RUN apt-get install -y \
    python3-dev \
    libcairo2-dev \
    pkg-config

RUN npm install -g pyright@1.1.411

ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv --system-site-packages $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN pip install git+https://gitlab.com/gajim/release-helper.git
RUN pip install --no-cache-dir -r requirements.txt

CMD bash
