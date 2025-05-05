#!/bin/sh

####################################################################
# Created by wannoo on 2019/07/25
# 设备管理基本信息
####################################################################

BRAND="Silent Angel"
# MODEL="M1"
MODEL=$(m1-model)

# IOS需要 Device Settings 的全部数据
function t_setting_info(){
	echo -n "{"
	echo -n "\"general\":$(t_general_info)"
	echo -n ",\"dac\":$(t_dac_info)"
	echo -n ",\"usb\":$(t_usb_info)"
	echo "}"
}

# Device Settings - General
function t_general_info(){
	echo -n "{"
	echo -n "\"brand\":\"${BRAND}\",\"model\":\"$(t_model)\""
	echo -n ",\"device_name\":\"$(t_device_name)\""
	echo -n ",$(sh /srv/sh/app_dac.sh in_use),$(sh /srv/sh/app_dac.sh usb_details)"
	echo "}"
}

function t_model(){
	m=$(m1-type 2>/dev/null | sed -n '1p')
	if [[ -z ${m} ]]; then
		m="${MODEL}"
	fi
	echo "${m}"
}

# 获取设备名称 M1-加上mac后六位
function t_device_name(){
	if [[ -e "/mnt/settings/hostname" ]]; then
		head -1 "/mnt/settings/hostname" 2>/dev/null
		return 0
	fi
	mac=$(cat /sys/class/net/eth0/address | sed 's@:@@g' | tr '[:lower:]' '[:upper:]' 2> /dev/null)
	echo "${MODEL}-${mac: -6}"
}

# 设置设备名称
function t_device_name_set(){
	if [[ -z ${1} ]]; then
		echo "101"
		return 1
	fi
	alias urldecode='sed "s@+@ @g;s@%@\\\\x@g" | xargs -0 printf "%b"'
	device_name=$(echo "${1}" | grep -Po 'device_name[=]+\K[^&]+' | urldecode)
	if [[ -z ${device_name} ]]; then
		echo "102"
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
	if [[ ! -d "/mnt/settings" ]]; then
		mkdir -p "/mnt/settings" >/dev/null 2>&1
	fi
	echo "${device_name}"
	echo -n "${device_name}" > "/mnt/settings/hostname"
	return $?
}

# Device Settings - Internal DAC & Digital Output
# m1-dac-output-conf
# 获取
# m1-dac-output-conf dsd-dop
# m1-dac-output-conf pcm-sample-rate
# m1-dac-output-conf pcm-bit-depth
# m1-dac-output-conf dsd-format
# 设置
# m1-dac-output-conf default yes 全部恢复为默认
# m1-dac-output-conf dsd-dop yes(pcm)
# m1-dac-output-conf pcm-sample-rate 384000(352800 192000 176400 96000 88200 48000 44100)
# m1-dac-output-conf pcm-bit-depth 32(24 16)
# m1-dac-output-conf dsd-format 128(64)
# 
# m1-dac-volume-ctl 当前能否设置音量
# 返回 0：不能设置音量；1：可以设置音量
# 传入参数 0 不能调节；1 可以调节
# 
# roon_software 控制音量开关
# /mnt/roon-ready/software 判断下有没有这个文件，有这个文件是打开的0，没有是关闭的1，默认没有
# 传入参数 roon_software 0:设置为 Enable 1:设置为 Disabled
function t_dac_info(){
	echo -n "{"
	echo -n "\"dsd_playback\":\"$(m1-dac-output-conf dsd-dop 2>/dev/null | sed -n '1p')\""
	echo -n ",\"sample_rate\":\"$(m1-dac-output-conf pcm-sample-rate 2>/dev/null | sed -n '1p')\""
	echo -n ",\"bit_rate\":\"$(m1-dac-output-conf pcm-bit-depth 2>/dev/null | sed -n '1p')\""
	echo -n ",\"dsd_format\":\"$(m1-dac-output-conf dsd-format 2>/dev/null | sed -n '1p')\""
	# echo -n ",\"dac_filter\":\"DSD-over-PCM(DoP)\""
	echo -n ",\"volume_control\":\"$(m1-dac-volume-ctl 2>/dev/null | sed -n '1p')\""

	[[ -e "/mnt/roon-ready/software" ]] && local software="0" || local software="1"
	echo -n ",\"roon_software\":\"${software}\""
	echo "}"
}

function t_dac_info_set(){
	if [[ -z ${1} ]]; then
		echo "101"
		return 9
	fi
	alias urldecode='sed "s@+@ @g;s@%@\\\\x@g" | xargs -0 printf "%b"'
	default=$(echo "${1}" | grep -Po 'default[=]+\K[^&]+' | urldecode)
	if [[ -n "${default}" ]]; then
		msg=$(m1-dac-output-conf default ${default} 2>&1)
		return $?
	fi
	dsd_playback=$(echo "${1}" | grep -Po 'dsd_playback[=]+\K[^&]+' | urldecode)
	if [[ -n "${dsd_playback}" ]]; then
		msg=$(m1-dac-output-conf dsd-dop "${dsd_playback}" 2>&1)
		return $?
	fi
	sample_rate=$(echo "${1}" | grep -Po 'sample_rate[=]+\K[^&]+' | urldecode)
	if [[ -n "${sample_rate}" ]]; then
		msg=$(m1-dac-output-conf pcm-sample-rate "${sample_rate}" 2>&1)
		return $?
	fi
	bit_rate=$(echo "${1}" | grep -Po 'bit_rate[=]+\K[^&]+' | urldecode)
	if [[ -n "${bit_rate}" ]]; then
		msg=$(m1-dac-output-conf pcm-bit-depth "${bit_rate}" 2>&1)
		return $?
	fi
	dsd_format=$(echo "${1}" | grep -Po 'dsd_format[=]+\K[^&]+' | urldecode)
	if [[ -n "${dsd_format}" ]]; then
		msg=$(m1-dac-output-conf dsd-format "${dsd_format}" 2>&1)
		return $?
	fi
	volume_control=$(echo "${1}" | grep -Po 'volume_control[=]+\K[^&]+' | urldecode)
	if [[ -n "${volume_control}" ]]; then
		if [[ "M1T" == "${MODEL}" ]]; then	#M1T不让设置音量开关
			echo "108"
			return 8
		fi
		msg=$(m1-dac-volume-ctl "${volume_control}" 2>&1)
		return $?
	fi
	roon_software=$(echo "${1}" | grep -Po 'roon_software[=]+\K[^&]+' | urldecode)
	if [[ -n ${roon_software} ]]; then
		file="/mnt/roon-ready/software"
		if [[ "0" == "${roon_software}" ]]; then
			touch "${file}" > /dev/null 2>&1
		else
			rm -rf  "${file}" > /dev/null 2>&1
		fi
		if [[ "0" == $(m1-dac-use 2>/dev/null | sed -n '1p') ]]; then
			m1-roon-ready-init > /dev/null 2>&1
			return $?
		fi
		return 0
	fi
	echo "102"
	return 8

}

# Device Settings - USB Audio
# m1-usb-dac-output-conf
# 获取
# m1-usb-dac-output-conf dsd-dop
# m1-usb-dac-output-conf pcm-sample-rate
# m1-usb-dac-output-conf pcm-bit-depth
# m1-usb-dac-output-conf dsd-format
# 设置
# m1-usb-dac-output-conf default yes 全部恢复为默认
# m1-usb-dac-output-conf dsd-dop yes(no pcm)
# m1-usb-dac-output-conf pcm-sample-rate 768000(705600 384000 352800 192000 176400 96000 88200 48000 44100)
# m1-usb-dac-output-conf pcm-bit-depth 32(24 16)
# m1-usb-dac-output-conf dsd-format 256(128 64)
# 
# m1-usb-dac-volume-ctl 当前能否设置音量
# 返回 0：不能设置音量；1：可以设置音量
# 传入参数 0 不能调节；1 可以调节
function t_usb_info(){
	echo -n "{"
	echo -n "\"dsd_playback\":\"$(m1-usb-dac-output-conf dsd-dop 2>/dev/null | sed -n '1p')\""
	echo -n ",\"sample_rate\":\"$(m1-usb-dac-output-conf pcm-sample-rate 2>/dev/null | sed -n '1p')\""
	echo -n ",\"bit_rate\":\"$(m1-usb-dac-output-conf pcm-bit-depth 2>/dev/null | sed -n '1p')\""
	echo -n ",\"dsd_format\":\"$(m1-usb-dac-output-conf dsd-format 2>/dev/null | sed -n '1p')\""
	echo -n ",\"volume_control\":\"$(m1-usb-dac-volume-ctl 2>/dev/null | sed -n '1p')\""

	[[ -e "/mnt/roon-ready/usb-software" ]] && local software="0" || local software="1"
	echo -n ",\"roon_software\":\"${software}\""
	echo "}"
}

function t_usb_info_set(){
	if [[ -z ${1} ]]; then
		echo "101"
		return 9
	fi
	alias urldecode='sed "s@+@ @g;s@%@\\\\x@g" | xargs -0 printf "%b"'
	default=$(echo "${1}" | grep -Po 'default[=]+\K[^&]+' | urldecode)
	if [[ -n "${default}" ]]; then
		msg=$(m1-usb-dac-output-conf default ${default} 2>&1)
		return $?
	fi
	dsd_playback=$(echo "${1}" | grep -Po 'dsd_playback[=]+\K[^&]+' | urldecode)
	if [[ -n "${dsd_playback}" ]]; then
		msg=$(m1-usb-dac-output-conf dsd-dop "${dsd_playback}" 2>&1)
		return $?
	fi
	sample_rate=$(echo "${1}" | grep -Po 'sample_rate[=]+\K[^&]+' | urldecode)
	if [[ -n "${sample_rate}" ]]; then
		msg=$(m1-usb-dac-output-conf pcm-sample-rate "${sample_rate}" 2>&1)
		return $?
	fi
	bit_rate=$(echo "${1}" | grep -Po 'bit_rate[=]+\K[^&]+' | urldecode)
	if [[ -n "${bit_rate}" ]]; then
		msg=$(m1-usb-dac-output-conf pcm-bit-depth "${bit_rate}" 2>&1)
		return $?
	fi
	dsd_format=$(echo "${1}" | grep -Po 'dsd_format[=]+\K[^&]+' | urldecode)
	if [[ -n "${dsd_format}" ]]; then
		msg=$(m1-usb-dac-output-conf dsd-format "${dsd_format}" 2>&1)
		return $?
	fi
	volume_control=$(echo "${1}" | grep -Po 'volume_control[=]+\K[^&]+' | urldecode)
	if [[ -n "${volume_control}" ]]; then
		msg=$(m1-usb-dac-volume-ctl "${volume_control}" 2>&1)
		return $?
	fi
	roon_software=$(echo "${1}" | grep -Po 'roon_software[=]+\K[^&]+' | urldecode)
	if [[ -n ${roon_software} ]]; then
		file="/mnt/roon-ready/usb-software"
		if [[ "0" == "${roon_software}" ]]; then
			touch "${file}" > /dev/null 2>&1
		else
			rm -rf  "${file}" > /dev/null 2>&1
		fi
		if [[ "0" != $(m1-dac-use 2>/dev/null | sed -n '1p') ]]; then
			m1-roon-ready-init > /dev/null 2>&1
			return $?
		fi
		return 0
	fi
	echo "102"
	return 8
}

# About 页面
function t_about_info(){
	echo -n "{"
	echo -n "\"brand\":\"${BRAND}\",\"model\":\"$(t_model)\""
	echo -n ",\"device_name\":\"$(t_device_name)\""
	echo -n ",\"serial_number\":\"$(t_serial_number)\""
	echo -n ",$(get_version_local_info)"
	echo -n ",$(get_running_time)"
	 . /srv/sh/app_network.sh
	echo -n ",$(get_ip_address),$(get_mac_address)"
	echo "}"
}

function t_serial_number(){
	serial=$(cat /mnt/settings/serial_number 2>/dev/null)
	if [[ -z ${serial} ]]; then
		serial="${MODEL}-$(cat /sys/class/net/eth0/address 2> /dev/null| sed 's/:/-/g'| tr 'a-z' 'A-Z')"
	fi
	echo "${serial}"
}

#获取当前设备版本
function get_version_local_info(){
	local version=$(thunder_version 2>/dev/null)
	echo "\"versions_local\":\"VitOS-$(echo ${version} | awk -v FS="-" '{print $2}')\""
}

#获取当前设备名
function get_device_name(){
	if [[ -e "/mnt/settings/hostname" ]]; then
		head -1 "/mnt/settings/hostname" 2>/dev/null
		return 0
	fi
	mac=$(cat /sys/class/net/eth0/address | sed 's@:@@g' | tr '[:lower:]' '[:upper:]' 2> /dev/null)
	echo "${MODEL}-${mac: -6}"
}

#获取当前设备名
function get_device_name_info(){
	echo -n "\"device_name\":\"$(get_device_name)\""
}

#获取当前系统已运行时间,单位秒	示例返回:120
function get_running_time(){
	local time=$(cat "/proc/uptime" | awk '{ printf( "%u",$1)}' | grep -E -o "[0-9]*")
	if [[ -z ${time} ]]; then
		time=0
	fi
	echo "\"run_time\":\"${time}\""
}

#返回首页需要的全部数据
function get_device_all(){
	echo -n "\"model\":\"Raspberry Pi\","
	echo -n "$(get_version_local_info),"
	echo -n "$(get_device_name_info),"
	echo -n "$(get_running_time),"
	. "/srv/sh/app_network.sh" > /dev/null
	echo -n "\"new_ip\":\"$(inspect_network_log ${1})\","
	echo -n "$(get_network_info),"
	. "/srv/sh/app_storage.sh" > /dev/null
	echo -n "$(get_sata_info),"
	. "/srv/sh/app_roon_bridge.sh" > /dev/null
	echo -n "$(get_roon_info)"
}

case "${1}" in
	"setting" )		# IOS需要 Device Settings 的全部数据
		t_setting_info
		exit $?
		;;
	"general" )		# Device Settings - General 页面需要的信息
		t_general_info
		exit $?
		;;
	"name" )		# 获取设备名称
		t_device_name
		exit $?
		;;
	"name_set" )		#设置设备名称
		msg=$(t_device_name_set "${2}")
		rtn=$?
		echo "{\"status\":${rtn},\"message\":\"${msg}\"}"
		exit $?
		;;
	"dac" )		# Device Settings - Internal DAC & Digital Output 页面需要的信息
		t_dac_info
		exit $?
		;;
	"dac_set" )		# Device Settings - Internal DAC & Digital Output 设置
		msg=$(t_dac_info_set "${2}")
		rtn=$?
		echo "{\"status\":${rtn},\"message\":\"${msg}\"}"
		exit $?
		;;
	"usb" )		# Device Settings - USB Audio 页面需要的信息
		t_usb_info
		exit $?
		;;
	"usb_set" )		# Device Settings - USB Audio 设置
		msg=$(t_usb_info_set "${2}")
		rtn=$?
		echo "{\"status\":${rtn},\"message\":\"${msg}\"}"
		exit $?
		;;
	"serial" )		# 设备序列号
		t_serial_number
		exit $?
		;;
	"about" )		# About 页面需要的信息
		t_about_info
		exit $?
		;;
esac