#!/bin/bash

git pull origin master

git add .

msg="update  "$(date)
echo $msg

git commit -m "$d"

git push origin master
