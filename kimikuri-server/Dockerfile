FROM python:3.9

ARG pip_source=https://pypi.python.org/simple

WORKDIR /kimikuri

COPY ./kuri ./kuri
COPY ./kimikuri.py .
COPY ./requirements.txt .

RUN pip install -r requirements.txt -i ${pip_source}

EXPOSE 8080

CMD uvicorn kimikuri:webapi --host 0.0.0.0 --port 8080