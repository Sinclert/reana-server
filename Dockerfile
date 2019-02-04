# This file is part of REANA.
# Copyright (C) 2017, 2018 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

FROM python:3.6

RUN apt-get update && \
    apt-get install -y vim-tiny

COPY CHANGES.rst README.rst setup.py /code/
COPY reana_server/version.py /code/reana_server/
RUN pip install -e git://github.com/reanahub/reana-commons.git@238-disk-usage#egg=reana-commons
WORKDIR /code
RUN pip install --no-cache-dir requirements-builder && \
    requirements-builder -e all -l pypi setup.py | pip install --no-cache-dir -r /dev/stdin && \
    pip uninstall -y requirements-builder

COPY . /code

# Debug off by default
ARG DEBUG=false

RUN if [ "${DEBUG}" = "true" ]; then pip install -r requirements-dev.txt; pip install -e .; else pip install .; fi;

ARG UWSGI_PROCESSES=2
ENV UWSGI_PROCESSES ${UWSGI_PROCESSES:-2}
ARG UWSGI_THREADS=2
ENV UWSGI_THREADS ${UWSGI_THREADS:-2}
ENV TERM=xterm
ENV FLASK_APP=/code/reana_server/app.py

EXPOSE 5000

CMD set -e && flask db init && \
    flask users create_default info@reana.io &&\
    uwsgi --module reana_server.app:app \
    --http-socket 0.0.0.0:5000 --master \
    --processes ${UWSGI_PROCESSES} --threads ${UWSGI_THREADS} \
    --stats /tmp/stats.socket \
    --wsgi-disable-file-wrapper
