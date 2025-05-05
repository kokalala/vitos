#!/bin/sh

# 监听/media/record文件夹是否添加新的U盘记录文件

RECORD_PATH="/media/record"		#记录U盘挂载信息
if [[ ! -d "${RECORD_PATH}" ]]; then
	mkdir -p "${RECORD_PATH}"
fi

inotifywait -mq --format '%f' -e create "${RECORD_PATH}" | while read dir ; do
	sh "/srv/sh/app_usb.sh" "auto_add" "${dir}" > /tmp/vitos_notify_usb_${dir}_create_link.log  2>&1
	echo "创建${dir}记录文件"
done
