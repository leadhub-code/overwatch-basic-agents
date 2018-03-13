FROM python:3.6-alpine

RUN apk add --no-cache --update python-dev py-pip gcc build-base linux-headers

COPY . /overwatch-basic-agents/

RUN pip install /overwatch-basic-agents

