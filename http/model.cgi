#!/bin/sh

####################################################################
# 设置model使用的
# 需要传入密码 password 和 model
####################################################################

echo -e "Content-type: text/plain;charset=utf-8\n"

if [[ "POST" = ${REQUEST_METHOD} ]]; then
	read info -n ${CONTENT_LENGTH}
else
	info="${QUERY_STRING}"
fi

if [[ -z "${info}" ]]; then
	echo "{\"status\":1,\"message\":\"Parameter cannot be empty\"}"
	exit 1
fi

alias urldecode='sed "s@+@ @g;s@%@\\\\x@g" | xargs -0 printf "%b"'

password=$(echo "${info}" | grep -Po 'password[=]+\K[^&]+' | urldecode)
if [[ -z "${password}" ]]; then
	echo "{\"status\":2,\"message\":\"password cannot be empty\"}"
	exit 2
fi

if [[ "thunder" != "$(thunder_aes_cbc128 f3/5hYt/sb/z${password}g==)" ]]; then
	echo "{\"status\":2,\"message\":\"wrong password\"}"
	exit 2
fi

model=$(echo "${info}" | grep -Po 'model[=]+\K[^&]+' | urldecode)
if [[ -z "${model}" ]]; then
	echo "{\"status\":3,\"message\":\"model cannot be empty\"}"
	exit 3
fi

m1-model-set "${model}" > /dev/null 2>&1
rtn=$?
msg=$(echo ${model} | sed -n '1p' | sed 's@\\@\\\\@g' | sed 's@\"@\\\"@g')
echo "{\"status\":${rtn},\"message\":\"${msg}\"}"
exit ${rtn}
