#!/bin/bash

./build.sh
docker run -p 8080:80 \
   -e KURI_CONFIG_FILE="/mnt/kimikuri.json" \
   -e KURI_USERS_DB_FILE="/mnt/users.json" \
   -e KURI_LOG_FILE="/mnt/kimikuri.log" \
   -v ~/Dev/kuri:/mnt \
   --name kuri kimikuri