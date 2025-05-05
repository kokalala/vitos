#!/bin/sh

server="upmpdcli"

# 以json格式返回版本信息,运行状态,应用名称
function t_upmpdcli_info(){
	t_upmpdcli_status > /dev/null 2>&1
	echo "{\"status\":$?,\"message\":\"$(t_upmpdcli_name)\"}"
}

# 获取运行状态：不输出信息，只返回代码 
# 返回 0:正常运行  3或者其他按没有运行处理	5:运行错误
function t_upmpdcli_status(){
	systemctl status ${server} > /dev/null 2>&1 	#获取服务运行状态
	rtn=$?
	if [[ 3 -eq ${rtn} ]]; then
		if systemctl is-failed --quiet ${server} > /dev/null 2>&1; then
			return 5
		fi
	fi
	return $rtn	#直接把systemctl状态返回
}

# 设置状态 
# 控制文件 /mnt/upmpdcli/stop
# 传入参数 dlna_status 0:设置为 Enable 1:设置为 Disabled
function t_upmpdcli_status_set(){
	if [[ -z ${1} ]]; then
		echo "101"		#没有传递参数进来
		return 1
	fi
	alias urldecode='sed "s@+@ @g;s@%@\\\\x@g" | xargs -0 printf "%b"'
	status=$(echo "${1}" | grep -Po 'dlna_status[=]+\K[^&]+' | urldecode)
	if [[ -z ${status} ]]; then
		echo "102"		#没有传递名称进来
		return 1
	fi
	if [[ "1" == "${status}" ]]; then
		touch "/mnt/upmpdcli/stop" > /dev/null 2>&1
		systemctl stop ${server} > /dev/null 2>&1
	else
		rm -rf  "/mnt/upmpdcli/stop" > /dev/null 2>&1
		systemctl start ${server} > /dev/null 2>&1
	fi
	return $?
}

# 获取名称
function t_upmpdcli_name(){
	name=$(/bin/m1-dlna-renderer-friendlyname 2>/dev/null | sed -n '1p')
	echo "${name}" | sed 's@\t@ @g' | sed 's@\\@\\\\@g' | sed 's@\"@\\\"@g'
}

# 设置名称，長度限制 16個, 容許字符包括：大小寫英文字符(a-z, A-Z), 數字(0-9), dash (-)
# /bin/m1-dlna-renderer-friendlyname
# 传参 set name
# 不传参 get name
function t_upmpdcli_name_set(){
	if [[ -z ${1} ]]; then
		echo "101"		#没有传递名称进来
		return 1
	fi
	alias urldecode='sed "s@+@ @g;s@%@\\\\x@g" | xargs -0 printf "%b"'
	device_name=$(echo "${1}" | grep -Po 'device_name[=]+\K[^&]+' | urldecode)
	if [[ -z ${device_name} ]]; then
		echo "102"		#没有传递名称进来
		return 1
	fi
	if [[ ${#device_name} -gt 16 ]]; then
		echo "103"		#长度不能超过16
		return 1
	fi
	if [[ -n $(echo "${device_name}" | grep -E -o "[^A-Za-z0-9-]") ]]; then
		echo "104"		#内容限制字符范围在A-Za-z0-9-之间
		return 1
	fi
	/bin/m1-dlna-renderer-friendlyname "${device_name}" > /tmp/log_vitos_${server}_name_set 2>&1
	rtn=$?
	if [[ 0 -ne ${rtn} ]]; then
		echo "20${rtn}"
		return 2
	fi
	echo "${device_name}"
	return 0
}


case "${1}" in
	"info" )		#dlna状态
		t_upmpdcli_info
		;;
	"status_set" )		#状态设置
		msg=$(t_upmpdcli_status_set "${2}")
		rtn=$?
		echo -n "{\"status\":${rtn},\"message\":\"${msg}\"}"
		;;
	"name_set" )		#应用名设置
		msg=$(t_upmpdcli_name_set "${2}")
		rtn=$?
		echo -n "{\"status\":${rtn},\"message\":\"${msg}\"}"
		;;
	* )
		echo -n "{\"status\":98,\"message\":\"987\"}"		#指令错误
		exit 98
		;;
esac
exit $?