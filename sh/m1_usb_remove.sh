#!/bin/sh

# 拔出usb时，udev执行
# 传进来的参数为U盘位置，类似：sdc

if [[ ! -d "/tmp/log_vitos_usb" ]]; then
	mkdir "/tmp/log_vitos_usb"
fi
log="/tmp/log_vitos_usb/usb_remove_${name}.log"
echo -e "start at $(date +%s)\nvitos udev remove usb ${1}" > ${log}

# 删除软链和记录
sh "/srv/sh/app_usb.sh" "auto_remove" "${1}" >> ${log} 2>&1
# 卸载
systemd-mount -u "/media/${1}"* >> ${log} 2>&1
# 删除挂载的文件夹
rm -d "/media/${1}"* >> ${log} 2>&1
