#!/bin/bash

git pull origin master

git add .

msg="update  "$(date)
echo $msg

git commit -m "$msg"

git push origin master
