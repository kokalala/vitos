#!/bin/sh

####################################################################
# Created by wannoo on 2019/07/23
# 读取日志文件相关
####################################################################

function json_result(){
	msg=$(${1})
	res=$?
	echo "\"status\":${res},\"message\":\"${msg}\","
}

function analysis(){
	alias urldecode='sed "s@+@ @g;s@%@\\\\x@g" | xargs -0 printf "%b"'
	local query=$(echo "${1}" | urldecode)
	for str in ${query//&/ }		#使用&进行分割
	do
		local key=$(echo ${str%%=*})
		local value=$(echo ${str##*=})
		case "${key}" in
			"shoutcast" )		#设备管理
				sh "/srv/sh/app_shoutcast.sh"
				return 0
			;;
		esac
	done
	if [[ -z "${info}" ]]; then		#get参数没有正常解析出来
		echo "{\"code\":5}"
		return 5
	fi
	echo -n "{"
	echo -n "${info}"
	echo -n "\"code\":0"
	echo "}"
}

#第一个为get参数键值对
#第二个参数为当前请求的IP
analysis "${1}" "${2}"