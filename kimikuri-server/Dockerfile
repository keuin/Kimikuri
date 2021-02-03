FROM python:3.9-slim

ARG pip_source=https://pypi.python.org/simple

WORKDIR /kimikuri

COPY ./kuri ./kuri
COPY ./kimikuri.py .
COPY ./requirements.txt .

# some basic tools for alpine
#RUN echo -e "https://mirrors.aliyun.com/alpine/v3.7/main" > /etc/apk/repositories
#RUN apk update && apk upgrade
#RUN apk add --no-cache python3.9-dev \
#                       pkgconfig \
#                       git \
#                       gcc \
#                       openldap \
#                       libcurl \
#                       python3-dev \
#                       gpgme-dev \
#                       libc-dev \
#    && rm -rf /var/cache/apk/*
#RUN wget https://bootstrap.pypa.io/get-pip.py && python get-pip.py
#RUN pip install setuptools==30.1.0

RUN pip install -r requirements.txt -i ${pip_source}

EXPOSE 8080

CMD uvicorn kimikuri:webapi --host 0.0.0.0 --port 8080