#!/bin/sh

####################################################################
# Created by wannoo on 2019/07/23
# app和服务器交互
####################################################################

echo -e "Content-type: text/plain;charset=utf-8\n"
if [[ "POST" = ${REQUEST_METHOD} ]]; then
	read info -n ${CONTENT_LENGTH}
	python "/srv/py/post.py" "${info}"
fi
