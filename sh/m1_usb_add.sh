#!/bin/sh

# 插入usb时，udev执行
# 传进来的参数为U盘位置，类似：sdc

RECORD_PATH="/media/record/"		#记录U盘挂载信息

#挂载操作
# ${1} U盘位置 "sdc" 或 "sdc1"
function vitos_mount_usb(){
	folder="/media/${1}"
	mkdir ${folder}

	# 挂载
	systemd-mount --no-block --collect --fsck=no "/dev/${1}" "${folder}" -o user,rw,umask=000,iocharset=utf8 >> ${log} 2>&1
	
	if [[ -e "${RECORD_PATH}${1}" ]]; then
		rm "${RECORD_PATH}${1}"
	fi
	#记录U盘的ptuuid和serial
	echo -e "${ptuuid}\n${serial}" > "${RECORD_PATH}${1}"
	
	echo -e "\tmount source /dev/${1} to directory ${folder}" >> ${log}
}

name=${1}		#sdc
name_full=${2}		#/dev/sdc
if [[ ! -d "/tmp/log_vitos_usb" ]]; then
	mkdir "/tmp/log_vitos_usb"
fi
log="/tmp/log_vitos_usb/usb_add_${name}.log"

if [[ ! -d "${RECORD_PATH}" ]]; then
	mkdir -p "${RECORD_PATH}"
fi

ptuuid=$(lsblk -no ptuuid -d ${name_full})
serial=$(lsblk -no serial -d ${name_full})

echo -e "start at $(date +%s)\nvitos udev add usb ${1} fullName ${2}\nptuuid:${ptuuid}\nserial:${serial}" > ${log}

i=0
for name_lsblk in $(lsblk -no NAME -d ${name_full}*); do
	if [[ ${name_lsblk} != ${name} ]]; then		#对分区进行尝试挂载
		vitos_mount_usb "${name_lsblk}"
		((i++))
	fi
done
if [[ 0 -eq ${i} ]]; then		#没有分区的U盘就尝试整个U盘挂载
	vitos_mount_usb "${name}"
fi

echo "finish at $(date +%s)" >> ${log}
