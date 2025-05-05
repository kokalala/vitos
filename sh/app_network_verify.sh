#!/bin/sh

####################################################################
# Created by wannoo on 2019/07/29
# 设置静态时验证上传的参数
####################################################################

#验证IP地址
function verify_ip(){
	if [[ -z "${1}" ]]; then
		echo "100"
		return 1
	fi
	echo "${1}" | grep -E -o "^([0-9]{1,3}[\.]){3}[0-9]{1,3}$" > /dev/null
	if [[ $? -ne 0 ]]; then
		echo "101"
		return 1
	fi
	arr=(${1//./ })
	for str in ${arr[@]}
	do
		if [[ ${str} -lt 0 ]] || [[ ${str} -gt 255 ]]; then
			echo "102"
			return 1
		fi
	done
	if [[ 127 -eq ${arr[0]} ]] && [[ 0 -eq ${arr[1]} ]] && [[ 0 -eq ${arr[2]} ]]; then
		echo "103"
		return 1
	fi
	if [[ ${arr[0]} -ge 224 ]] && [[ ${arr[0]} -le 239 ]]; then
		echo "104"
		return 1
	fi
	echo "${1}"
	return 0
}

#验证子网掩码
function verify_netmask(){
	if [[ -z "${1}" ]]; then
		echo "200"
		return 1
	fi
	echo "${1}" | grep -E -o "^([0-9]{1,3}[\.]){3}[0-9]{1,3}$" > /dev/null
	if [[ $? -ne 0 ]]; then
		echo "201"
		return 1
	fi
	echo "$(echo "${1}" | sed "s/000/0/g" | sed "s/00/0/g")"		#将多个0改成一个0
	return 0
}

#解析子网掩码
function verify_netmask_analysi(){
	case "${1}" in
		"0.0.0.0" )
			echo "0"
		;;
		"128.0.0.0" )
			echo "1"
		;;
		"192.0.0.0" )
			echo "2"
		;;
		"224.0.0.0" )
			echo "3"
		;;
		"240.0.0.0" )
			echo "4"
		;;
		"248.0.0.0" )
			echo "5"
		;;
		"252.0.0.0" )
			echo "6"
		;;
		"254.0.0.0" )
			echo "7"
		;;
		"255.0.0.0" )
			echo "8"
		;;
		"255.128.0.0" )
			echo "9"
		;;
		"255.192.0.0" )
			echo "10"
		;;
		"255.224.0.0" )
			echo "11"
		;;
		"255.240.0.0" )
			echo "12"
		;;
		"255.248.0.0" )
			echo "13"
		;;
		"255.252.0.0" )
			echo "14"
		;;
		"255.254.0.0" )
			echo "15"
		;;
		"255.255.0.0" )
			echo "16"
		;;
		"255.255.128.0" )
			echo "17"
		;;
		"255.255.192.0" )
			echo "18"
		;;
		"255.255.224.0" )
			echo "19"
		;;
		"255.255.240.0" )
			echo "20"
		;;
		"255.255.248.0" )
			echo "21"
		;;
		"255.255.252.0" )
			echo "22"
		;;
		"255.255.254.0" )
			echo "23"
		;;
		"255.255.255.0" )
			echo "24"
		;;
		"255.255.255.128" )
			echo "25"
		;;
		"255.255.255.192" )
			echo "26"
		;;
		"255.255.255.224" )
			echo "27"
		;;
		"255.255.255.240" )
			echo "28"
		;;
		"255.255.255.248" )
			echo "29"
		;;
		"255.255.255.252" )
			echo "30"
		;;
		"255.255.255.254" )
			echo "31"
		;;
		"255.255.255.255" )
			echo "32"
		;;
		* )
			echo "202"
			return 1
		;;
	esac
	return 0
}

#验证gateway
function verify_gateway(){
	if [[ -z "${1}" ]]; then
		echo "300"
		return 1
	fi
	echo "${1}" | grep -E -o "^([0-9]{1,3}[\.]){3}[0-9]{1,3}$" > /dev/null
	if [[ $? -ne 0 ]]; then
		echo "301"
		return 1
	fi
	echo "${1}"
	return 0
}

#验证dns
function verify_dns(){
	if [[ -z "${1}" ]]; then
		echo "400"
		return 1
	fi
	echo "${1}" | grep -E -o "^([0-9]{1,3}[\.]){3}[0-9]{1,3}$" > /dev/null
	if [[ $? -ne 0 ]]; then
		echo "401"
		return 1
	fi
	echo "${1}"
	return 0
}
