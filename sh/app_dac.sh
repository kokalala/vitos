#!/bin/sh



alias urldecode='sed "s@+@ @g;s@%@\\\\x@g" | xargs -0 printf "%b"'		#解码

# m1-dac-use 当前正在使用的dac
# 返回 0：m1-dac； 1：usb-dac
function vitos_dac_in_use(){
	echo -n "\"dac_use\":\"$(m1-dac-use 2>/dev/null | sed -n '1p')\""
}

# 设置使用的dac
# 传入参数 dac= m1 或 usbdac 或 其他
function vitos_dac_in_use_set(){
	if [[ -z "${1}" ]]; then
		echo "101"
		return 1
	fi
	dac=$(echo "${1}" | grep -Po 'dac[=]+\K[^&]+' | urldecode)
	if [[ -z "${dac}" ]]; then
		echo "102"
		return 2
	fi
	m1-dac-use "${dac}" 2>&1 | sed -n '1p' | sed 's@\\@\\\\@g' | sed 's@\"@\\\"@g'; test ${PIPESTATUS[0]} -eq 0
	return $?
}

# 获取USB DAC设备信息
# 传入参数为声卡序号,不传默认为最早插入的声卡
function vitos_usb_dac_details(){
	echo -n "\"usb_dac_details\":"		#输出信息
	dac_index=$(cat /proc/asound/cards 2>/dev/null | grep USB-Audio | grep ']:' | sed -n '1p' | awk '{print $1}')		#获取最早插入的usb dac
	if [[ ! -e "/proc/asound/card${dac_index}/usbid" ]]; then
		echo "null"		#找不到这个声卡的信息
		return 1
	fi
	echo -n "{"
	local name_all=$(cat /proc/asound/cards 2> /dev/null | grep ^" ${dac_index}"  -A 1 )
	local name=$(echo "${name_all}" | sed -n '1p'| cut -d "-"  -f 3- | sed 's/^[ \t]*//g')
	echo -n "\"name\":\"${name}\""

	local usbid=$(cat /proc/asound/card${dac_index}/usbid)
	local usbid_arr=(${usbid/:/ })
	local vendor_id=${usbid_arr[0]}
	local product_id=${usbid_arr[1]}

	local vendor_hwdb=$(grep -i ^"usb:v${vendor_id}\*" -A 1 "/lib/udev/hwdb.d/20-usb-vendor-model.hwdb")
	if [[ -z ${vendor_hwdb} ]]; then
		local name_full=$(echo "${name_all}" | sed -n '2p' | sed 's/^[ \t]*//g')
		vendor_name=$(echo "${name_full%${name}*}" | sed 's/[ \t]*$//g')
	else
		vendor_name=$(echo ${vendor_hwdb#*ID_VENDOR_FROM_DATABASE=})
	fi
	if [[ -z ${vendor_name} ]]; then
		vendor_name=$(echo ${name} | awk '{print $1}')
	fi

	echo -n ",\"vendor_name\":\"${vendor_name}\""
	echo -n ",\"product_name\":\"${name}\""
	echo -n ",\"vendor_id\":\"${vendor_id}\""
	echo -n ",\"product_id\":\"${product_id}\""
	local serial=$(ls -l /dev/snd/by-id/ | grep "../controlC${dac_index}"$ | awk '{print $9}' | cut -d "-" -f2 )
	echo -n ",\"serial\":\"$serial\""
	echo "}"
}

# m1-dac-volume-ctl 当前能否设置音量
# 返回 0：不能设置音量；1：可以设置音量
function vitos_volume_allow_adjust(){
	msg=$(m1-dac-volume-ctl  2>/dev/null | sed -n '1p')
	rtn=$?
	echo -n "\"allow_adjust_rtn\":${rtn},\"allow_adjust\":\"${msg}\""
}

# 设置能否设置音量
# 传入参数 adjust= 0 不能调节；1 可以调节
function vitos_volume_allow_adjust_set(){
	if [[ -z "${1}" ]]; then
		echo "101"
		return 1
	fi
	adjust=$(echo "${1}" | grep -Po 'adjust[=]+\K[^&]+' | urldecode | grep -E -o "[0-9]*")
	if [[ -z "${adjust}" ]]; then
		echo "102"
		return 2
	fi
	m1-dac-volume-ctl "${adjust}" 2>&1 | sed -n '1p' | sed 's@\\@\\\\@g' | sed 's@\"@\\\"@g'; test ${PIPESTATUS[0]} -eq 0
	return $?
}

case "${1}" in
	"dac_info" )		#当前正在使用的dac
		echo -n "{\"status\":0,\"message\":\"新年快乐\",$(vitos_dac_in_use),$(vitos_volume_allow_adjust)}"
		;;
	"in_use" )		#当前正在使用的dac
		vitos_dac_in_use
		;;
	"in_use_set" )		#设置使用的dac
		msg=$(vitos_dac_in_use_set "${2}")
		rtn=$?
		echo -n "{\"status\":${rtn},\"message\":\"${msg}\"}"
		;;
	"usb_details" )		#usb dac详细信息
		vitos_usb_dac_details
		;;
	"allow_adjust" )		#当前能否设置音量
		vitos_volume_allow_adjust
		;;
	"allow_adjust_set" )		#设置能否设置音量
		msg=$(vitos_volume_allow_adjust_set "${2}")
		rtn=$?
		echo -n "{\"status\":${rtn},\"message\":\"${msg}\"}"
		;;
	* )
		echo -n "{\"status\":98,\"message\":\"987\"}"		#指令错误
		exit 98
		;;
esac
exit $?
