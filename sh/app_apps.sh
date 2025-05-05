#!/bin/sh


alias urldecode='sed "s@+@ @g;s@%@\\\\x@g" | xargs -0 printf "%b"'

airplay="shairport-sync"
spotify="spotify-connect"
roonbridge="roon-ready"
switch_record="/mnt/settings/vitos_apps_switch_record"

# 当前使用的应用
function t_apps_use(){
	echo -n "{\"use\":\"$(m1-dac-play-app  2>/dev/null | sed -n '1p')\"}"
}

# 以json格式返回版本信息,运行状态,应用名称
function t_apps_info(){
	t_apps_status > /dev/null 2>&1
	echo -n "{\"status\":$?,\"message\":\"$(t_apps_name)\""
	if [[ "${roonbridge}" = "${server}" ]]; then
		[[ -e "/mnt/${roonbridge}/software" ]] && local software="0" || local software="1"
		echo -n ",\"software\":\"${software}\""
	fi
	echo -n ",\"use\":\"$(m1-dac-play-app  2>/dev/null | sed -n '1p')\""
	echo "}"
}

# 获取运行状态：不输出信息，只返回代码 
# 返回 0:正常运行  3或者其他按没有运行处理	5:运行错误
function t_apps_status(){
	systemctl status "${server}" > /dev/null 2>&1 	#获取服务运行状态

	rtn=$?
	if [[ 3 -eq ${rtn} ]]; then
		if systemctl is-failed --quiet ${server} > /dev/null 2>&1; then
			return 5
		fi
	fi
	return $rtn	#直接把systemctl状态返回
}

# 设置状态 
# 控制文件 /mnt/${server}/stop
# 传入参数 app_status 0:设置为 Enable 1:设置为 Disabled
function t_apps_status_set(){
	if [[ -z ${1} ]]; then
		echo "101"		#没有传递参数进来
		return 1
	fi
	status=$(echo "${1}" | grep -Po 'app_status[=]+\K[^&]+' | urldecode)
	if [[ -z ${status} ]]; then
		echo "102"		#没有传递名称进来
		return 1
	fi
	if [[ "1" == "${status}" ]]; then
		touch "/mnt/${server}/stop" > /dev/null 2>&1
		systemctl stop ${server} > /dev/null 2>&1
	else
		rm -rf  "/mnt/${server}/stop" > /dev/null 2>&1
		systemctl start ${server} > /dev/null 2>&1
	fi
	return $?
}

# 获取名称
function t_apps_name(){
	if [[ "${roonbridge}" = "${server}" ]]; then
		echo "Silent Angel $(m1-model)"
		return 0
	fi
	name=$(vitos_app_config -a "${server}" 2>/dev/null | sed -n '1p')
	echo "${name}" | sed 's@\t@ @g' | sed 's@\\@\\\\@g' | sed 's@\"@\\\"@g'
}

# 设置名称，長度限制 16個, 容許字符包括：大小寫英文字符(a-z, A-Z), 數字(0-9), dash (-)
function t_apps_name_set(){
	if [[ -z ${1} ]]; then
		echo "101"		#没有传递名称进来
		return 1
	fi
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
	vitos_app_config -a "${server}" -t name -v "${device_name}" > /tmp/log_vitos_${server}_name_set 2>&1
	rtn=$?
	if [[ 0 -ne ${rtn} ]]; then
		echo "20${rtn}"
		return 2
	fi
	systemctl status "${server}" > /dev/null 2>&1 	#获取服务运行状态
	if [[ 0 -eq $? ]]; then
		systemctl restart "${server}" > /dev/null 2>&1
	fi
	echo "${device_name}"
	return 0
}

# 控制音量开关,目前只有roon使用
# /mnt/roon-ready/software
# 你判断下有没有这个文件，有这个文件是打开的，没有是关闭的，默认没有
# 传入参数 app_software 0:设置为 Enable 1:设置为 Disabled
function t_apps_software_set(){
	if [[ -z ${1} ]]; then
		echo "101"		#没有传递参数进来
		return 1
	fi
	status=$(echo "${1}" | grep -Po 'app_software[=]+\K[^&]+' | urldecode)
	if [[ -z ${status} ]]; then
		echo "102"		#没有传递名称进来
		return 1
	fi
	file="/mnt/${server}/software"
	if [[ "0" == "${status}" ]]; then
		if [[ ! -e "${file}" ]]; then
			touch "${file}" > /dev/null 2>&1
			m1-${server}-init > /dev/null 2>&1
		fi
	else
		if [[ -e "${file}" ]]; then
			rm -rf  "/mnt/${server}/software" > /dev/null 2>&1
			m1-${server}-init > /dev/null 2>&1
		fi
	fi
	return 0
}

# 重启服务
function t_apps_restart(){
	systemctl restart "${server}" > /dev/null 2>&1 	#获取服务运行状态
	return $?
}



# 传入参数
# ${1}：应用服务名称 shairport-sync 或 spotify-connect 或 roon-ready
# ${2}：剩余其他get参数：如：control=name_set&device_name=wannoo

if [[ -z ${1} ]]; then
	echo "101"
	exit 4
fi
if [[ "${1}" = "use" ]]; then
	t_apps_use
	exit $?
fi

server="${1}"

control=$(echo "${2}" | grep -Po 'control[=]+\K[^&]+')
if [[ -z "${control}" ]]; then
	t_apps_info
	exit $?
fi

case "${control}" in
	"info" )		#dlna状态
		t_apps_info
		exit $?
		;;
	"status" )		#状态设置
		msg=$(t_apps_status)
		;;
	"status_set" )		#状态设置
		msg=$(t_apps_status_set "${2}")
		;;
	"name" )		#应用名设置
		msg=$(t_apps_name)
		;;
	"name_set" )		#应用名设置
		msg=$(t_apps_name_set "${2}")
		;;
	"software_set" )		#roon控制音量开关
		msg=$(t_apps_software_set "${2}")
		;;
	"restart" )		#应用名设置
		msg=$(t_apps_restart)
		;;
	* )
		if [[ -e "/srv/sh/app_apps_${server}.sh" ]]; then
			sh "/srv/sh/app_apps_${server}.sh" "${control}" "${2}"
		elif [[ -e "/mnt/${server}/app_apps_${server}.sh" ]]; then
			sh "/mnt/${server}/app_apps_${server}.sh" "${control}" "${2}"
		else
			echo -n "{\"status\":98,\"message\":\"987\"}"		#指令错误
			exit 98
		fi
		exit $?
		;;
esac
rtn=$?
echo -n "{\"status\":${rtn},\"message\":\"${msg}\"}"
exit ${rtn}