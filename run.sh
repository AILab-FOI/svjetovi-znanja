#!/usr/bin/env bash

echo -n "Enter your OpenAI API Key: "
stty -echo
type -p read >/dev/null && read OPENAI_API_KEY
stty echo
echo

export OPENAI_API_KEY="$OPENAI_API_KEY"

echo "Starting database ..."
cd server && rethinkdb &
sleep 1 

echo "Starting MMO server ..."
cd server && node mmo.js &
sleep 1 

echo "Starting Web server ..."
cd server && python3 openai-server.py

