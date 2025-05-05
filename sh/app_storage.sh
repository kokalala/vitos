#!/bin/sh

####################################################################
# Created by wannoo on 2019/06/05
# 存储操作相关
####################################################################


#将每bytes格式总容量按1000的比例将数据转成GB或TB展示
#传入参数：$1以B为单位的容量大小
function format_size(){
	[[ -z $2 ]] && local degree=0 || local degree=${2}
	if [[ ${degree} -gt 4 ]] 2>/dev/null ; then
		echo "${1}TB"
		return 0
	fi
	if [[ $1 -gt 999 ]] 2>/dev/null ; then
		local quotient=$(($1 / 1000))
		format_size ${quotient} $((${degree} + 1))
	else
		case ${degree} in
			0) echo "${1}B"
			;;
			1) echo "${1}KB"
			;;
			2) echo "${1}MB"
			;;
			3) echo "${1}GB"
			;;
			4) echo "${1}TB"
			;;
			*) echo "${1}"
			;;
		esac
	fi
	return 0
}

#将每KB大小的已使用容量按1024的比例将数据转成GB或TB展示,保留小数点后一位
#传入参数：$1以KB为单位的容量大小
function format_used_size(){
	[[ -z $2 ]] && local degree=0 || local degree=${2}
	if [[ ${degree} -gt 3 ]] 2>/dev/null ; then		#单位最大显示TB
		echo "${1}TB"
		return 0
	fi
	if [[ $(echo ${1%.*}) -gt 1023 ]] 2>/dev/null ; then		#去掉小数点后再比较
		local quotient=$(awk 'BEGIN{printf "%.1f\n",'$1'/1024}')		#商数保留一个小数点后数字
		format_used_size ${quotient} $((${degree} + 1))
	else
		case ${degree} in
			0) echo "${1}KB"
			;;
			1) echo "${1}MB"
			;;
			2) echo "${1}GB"
			;;
			3) echo "${1}TB"
			;;
			*) echo "${1}"
			;;
		esac
	fi
	return 0
}

#获取sata盘名称、型号、大小
function get_sata_info(){
	echo -n "\"sata\":{"
	echo -n "$(get_sata_info_sda)"
	echo -n "}"
}

function get_sata_info_sda(){
	local disk=$(lsblk -p -b -o NAME,MODEL,SIZE,TRAN -n | grep "^/dev/mmcblk0")
	local model=$(echo "${disk}" | awk '{print $2}' | sed "s/_/ /g" )		#获取设备型号，把下划线转成空格：HGST HTS541010B7E610、、、
	local size=$(format_size "$(echo "${disk}"| awk '{print $2}')")		#获取尺寸并格式化：1TB
	echo -en "\"sda\":{\"model\":\"${model}\",\"size\":\"${size}\",$(get_sata_available $(df | grep " /$" | awk '{print $1}'))}"
}

#通过sata盘挂载信息 获取总容量、剩余可使用容量、比例
function get_sata_available(){
	if [[ -z "${1}" ]]; then
		echo -en "\"status\":5"		#参数为空
		return 5
	fi
	local all=$(df | grep "^${1}" | awk '{print $2}')		#全部容量
	if [[ -z "${all}" ]]; then		#没有挂载
		echo -en "\"status\":1"
		return 1
	fi
	local sum_all=0
	for a in ${all}; do
		sum_all=$((${sum_all} + ${a}))
	done
	local available=$(df | grep "^${1}" | awk '{print $4}')		#剩余
	local sum_available=0
	for av in ${available}; do
		sum_available=$((${sum_available} + ${av}))
	done
	echo -en "\"status\":0"		#有正常挂载
	echo -en ",\"all\":\"$(format_used_size ${sum_all} | sed "s/[.][0-9]//g")\""		#总容量:展示920.5GB转成920GB
	echo -en ",\"available\":\"$(format_used_size ${sum_available})\""		#剩余可用:888.8GB
	if [[ 0 != ${sum_all} ]]; then
		echo -en ",\"ratio\":\"$((${sum_available}*100/${sum_all}))\""		#可用比例:95		
	fi
	return 0
}
