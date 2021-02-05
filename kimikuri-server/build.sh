#!/bin/bash

docker kill kuri
docker image rm kuri
docker build -t kuri .