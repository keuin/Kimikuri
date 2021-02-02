FROM python:3.9

WORKDIR /kimikuri

COPY ./kuri ./kuri
COPY ./kimikuri.py .
COPY ./requirements.txt .

RUN pip install -r requirements.txt

EXPOSE 80

CMD uvicorn kimikuri:webapi --host 0.0.0.0 --port 80