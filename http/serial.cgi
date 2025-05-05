#!/bin/sh

####################################################################
# 填写序列号使用的
# 需要传入密码
####################################################################

echo -e "Content-type: text/plain;charset=utf-8\n"

if [[ "POST" = ${REQUEST_METHOD} ]]; then
	read info -n ${CONTENT_LENGTH}
else
	info="${QUERY_STRING}"
fi

if [[ -z "${info}" ]]; then
	echo "Parameter cannot be empty"
	exit 1
fi

alias urldecode='sed "s@+@ @g;s@%@\\\\x@g" | xargs -0 printf "%b"'

password=$(echo "${info}" | grep -Po 'password[=]+\K[^&]+' | urldecode)
if [[ -z "${password}" ]]; then
	echo "password cannot be empty"
	exit 2
fi

if [[ "thunder" != "$(thunder_aes_cbc128 f3/5hYt/sb/z${password}g==)" ]]; then
	echo "wrong password"
	exit 2
fi

serial=$(echo "${info}" | grep -Po 'serial[=]+\K[^&]+' | urldecode)
if [[ -z "${serial}" ]]; then
	serial="M1-$(cat /sys/class/net/eth0/address 2> /dev/null| sed 's/:/-/g'| tr 'a-z' 'A-Z')"
fi
if [[ -z "${serial}" ]]; then
	echo "serial cannot be empty"
	exit 3
fi

echo "${serial}" > "/mnt/settings/serial_number"
echo "Serial(${serial}) successfully writes"
exit 0