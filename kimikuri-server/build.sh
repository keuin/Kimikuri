#!/bin/bash

docker kill kuri
docker rm kuri
docker build -t kuri .