FROM debian:unstable-slim

RUN apt-get update
RUN apt-get -y install apt-utils
RUN apt-get -y install \
    build-essential \
    debhelper \
    wget \
    git \
    gnupg \
    gettext \
    dh-python \
    pybuild-plugin-pyproject \
    libglib2.0-dev \
    python3-all \
    python3-build \
    python3-cryptography \
    python3-css-parser \
    python3-gi-cairo \
    python3-idna \
    python3-packaging \
    python3-pil \
    python3-pip \
    python3-precis-i18n \
    python3-protobuf \
    python3-qrcode \
    python3-setuptools \
    python3-venv \
    python3-emoji \
    python3-sqlalchemy \
    python3-keyring \
    python3-httpx2 \
    python3-h2 \
    python3-truststore \
    python3-pysequoia \
    gir1.2-adw-1 \
    gir1.2-gst-plugins-base-1.0 \
    gir1.2-gstreamer-1.0 \
    gir1.2-gtk-4.0 \
    gir1.2-gtksource-5 \
    gir1.2-soup-3.0

RUN pip install --break-system-packages git+https://gitlab.com/gajim/release-helper.git

RUN wget -qO- https://gajim.org/gajim.key | tee /etc/apt/trusted.gpg.d/gajim.asc
RUN echo deb https://ftp.gajim.org/debian unstable main > /etc/apt/sources.list.d/nbxmpp.list

CMD bash
