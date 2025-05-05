#!/bin/sh

RECORD_PATH="/media/record/"		#记录U盘挂载信息
MPD_PATH="/mnt/mpd/music/usb/"		#U盘音乐存放路径

SETTING_DIR="/mnt/settings/"
LIST_USB_DISABLE="${SETTING_DIR}vitos_usb_disable_record"		#记录禁用的U盘信息

# U盘插入时自动执行软链接创建
# ${1} U盘挂载时在/mnt/mpd/music/usb创建的文件夹，如：sdc1 或sdc
function vitos_usb_auto_add(){
	if [[ -z ${1} ]]; then
		echo "没有传参数"
		return
	fi
	if [[ ! -d "${MPD_PATH}" ]]; then
		mkdir -p "${MPD_PATH}"
	fi
	if [[ ! -d "${SETTING_DIR}" ]]; then
		mkdir -p "${SETTING_DIR}"
	fi
	echo "###start###"

	dev="/dev/${1}"
	mountpoint="/media/${1}"

	file=${RECORD_PATH}${1}		#记录ptuuid和serial的文件
	ptuuid=$(head -1 ${file} 2>/dev/null)
	serial=$(sed -n 2p ${file} 2>/dev/null)

	k=0
	while [[ ${k} -lt 100 ]]; do
		uuid=$(lsblk -no uuid -d ${dev})
		if [[ -z ${uuid} ]]; then
			((k++))		#刚插入没那么快拿到UUID
			continue
		fi
		echo "while k=${k} uuid:${uuid}"
		is_disable=$(grep -En ^"PTUUID=\"${ptuuid}\" SERIAL=\"${serial}\" UUID=\"${uuid}\"" "${LIST_USB_DISABLE}" 2>/dev/null)
		if [[ -n ${is_disable} ]]; then
			echo "USB partition is disabled #分区已被禁用"
			return		#U盘被禁用直接结束任务
		fi
		#文件夹名称使用label和uuid前8位
		label1=$(lsblk -no label -d ${dev})
		label=$(python3 "/srv/py/app_str_decode.py" "${label1}" 2>/dev/null)		#使用python3对中文分区名称转码
		if [[ -z ${label} ]]; then
			dir="No Label_$(echo ${uuid:0:8})"
		else
			dir="${label}_$(echo ${uuid:0:8})"
		fi
		folder="${MPD_PATH}${dir}"

		if [[ -e "${folder}" ]] && [[ -z $(ls -l "${folder}" 2> /dev/null | grep " ${mountpoint}"$) ]]; then
			i=0		#文件夹名称有存在一样的,就递归创建新的文件夹名称
			while [[ true ]]; do
				if [[ ${i} -lt 10 ]]; then
					i2="00${i}"
				elif [[ ${i} -lt 100 ]]; then
					i2="0${i}"
				else
					i2="${i}"
				fi
				folder_path="${folder}_${i2}"

				if [[ ${i} -gt 10 ]] || [[ ! -d ${folder_path} ]] || [[ -n $(ls -l "${folder_path}" 2> /dev/null | grep " -> ${mountpoint}$") ]]; then
					folder="${folder_path}"
					break
				fi
				((i++))
			done
		fi

		ln -snf "${mountpoint}" "${folder}"
		echo "#${?}#ln -snf ${mountpoint} ${folder}"

		w=0
		while [[ ${w} -lt 100 ]]; do
			if [[ -n $(ls "${folder}" 2> /dev/null) ]]; then
				echo "while w=${w} ${folder} not empty"
				break
			fi
			((w++))
		done
		mpc update "usb/${dir}"
		echo "#${?}#mpc update usb/${dir}"
		return
	done
	echo "还是没获取到UUID"
	if [[ -z ${uuid} ]] && [[ -z $(echo ${1} | grep -E -o "[0-9]*") ]]; then
		echo "没有分区的U盘 ${dev}"
		partx -a ${dev}	# 解析分区表
		j=0
		for name in $(lsblk -no name -d ${dev}* | grep -v ^"${1}"$); do
			((j++))
			dev_child="/dev/${name}"
			mountpoint_child="/media/${name}"
			mkdir ${mountpoint_child}
			mount ${dev_child} ${mountpoint_child}  -o user,rw,umask=000,iocharset=utf8
			rtn=$?
			if [[ 0 -eq ${rtn} ]]; then
				uuid=$(lsblk -no uuid -d ${dev_child})
				if [[ -z ${uuid} ]]; then
					continue
				fi
				echo "uuid:${uuid}"
				vitos_usb_auto_add_ln
			fi
		done
		if [[ 0 -eq ${j} ]]; then		#没有分区的U盘就尝试整个U盘挂载
			dev_child="/dev/${1}"
			mountpoint_child="/media/${1}"
			vitos_usb_auto_add_ln
		fi
	fi
}

# 解析分区表后尝试挂载和软链
function vitos_usb_auto_add_ln(){
	is_disable=$(grep -En ^"PTUUID=\"${ptuuid}\" SERIAL=\"${serial}\" UUID=\"${uuid}\"" "${LIST_USB_DISABLE}" 2>/dev/null)
	if [[ -n ${is_disable} ]]; then
		echo "USB partition is disabled #分区已被禁用"
		return		#U盘被禁用直接结束任务
	fi
	#文件夹名称使用label和uuid前8位
	label1=$(lsblk -no label -d ${dev_child})
	label=$(python3 "/srv/py/app_str_decode.py" "${label1}" 2>/dev/null)		#使用python3对中文分区名称转码
	if [[ -z ${label} ]]; then
		dir="No Label_$(echo ${uuid:0:8})"
	else
		dir="${label}_$(echo ${uuid:0:8})"
	fi
	folder="${MPD_PATH}${dir}"

	if [[ -e "${folder}" ]] && [[ -z $(ls -l "${folder}" 2> /dev/null | grep " ${mountpoint_child}"$) ]]; then
		i=0		#文件夹名称有存在一样的,就递归创建新的文件夹名称
		while [[ true ]]; do
			if [[ ${i} -lt 10 ]]; then
				i2="00${i}"
			elif [[ ${i} -lt 100 ]]; then
				i2="0${i}"
			else
				i2="${i}"
			fi
			folder_path="${folder}_${i2}"

			if [[ ${i} -gt 10 ]] || [[ ! -d ${folder_path} ]] || [[ -n $(ls -l "${folder_path}" 2> /dev/null | grep " -> ${mountpoint_child}$") ]]; then
				folder="${folder_path}"
				break
			fi
			((i++))
		done
	fi

	ln -snf "${mountpoint_child}" "${folder}"
	echo "#${?}#ln -snf ${mountpoint_child} ${folder}"
}

# U盘拔掉时自动执行软链删除
# ${1} U盘位置 类似：sdc
# 如果没有传入参数删除所有/media链接过来的文件夹
function vitos_usb_auto_remove(){
	echo "任务开始 ${1}"

	rm "/media/record/${1}"*
	[[ -z ${1} ]] && mountpoint="/media/.*" || mountpoint="/media/${1}[0-9]*"

	local IFS_old=$IFS
	IFS=$'\n'
	for dir in $(echo "$(ls -l "${MPD_PATH}" 2> /dev/null)" | grep " -> ${mountpoint}$" | sed "s| -> ${mountpoint}$||"); do
		dir=$(echo "${dir}" | awk -F " " '{for (i=9;i<=NF;i++)printf("%s ", $i);print ""}' | sed 's| $||')
		if [[ -n "${dir}" ]]; then
			folder="${MPD_PATH}${dir}"
			rm -d "${folder}"
			echo "删除文件夹 ${folder}"
		fi
	done
	IFS=$IFS_old
	
	echo "任务结束 ${mountpoint}"
}

# 输出全部已挂载的U盘的分区信息
# {"status": 0,"message": "message",
# "enable_list":[{"ptuuid": "72ac64d5","serial": "0C9D9282","uuid": "404E-0B30","model": "ler 3.0","label": "FA TT","fssize": "2G","mountpoint": "/media/sda2","index": "2","path": ""}],
# "disable_list":[{"ptuuid": "64d72ac5","serial": "20D869219C","uuid": "0B30404E","model": "DataT","label": "fa","fssize": "1024M","mountpoint": "/media/sdb","index": "0","path": ""}]
# }
function vitos_usb_mount_list(){
	enable_list=""
	disable_list=""

	local IFS_old=$IFS
	IFS=$'\n'
	for line in $(lsblk -P -o tran,name,ptuuid,serial,vendor,model,uuid,label,fssize,mountpoint 2>/dev/null); do
		if [[ ${line} =~ ^'TRAN="usb" ' ]]; then		#只处理U盘
			usb_name=$(echo "${line}" | grep -Po ' NAME="+\K[^" ]+' | sed -n '1p' | sed 's@\\@\\\\@g' | sed 's@\"@\\\"@g')		#U盘位置，类似 sdc
			ptuuid=$(echo "${line}" | grep -Po ' PTUUID="+\K[^" ]+' | sed -n '1p' | sed 's@\\@\\\\@g' | sed 's@\"@\\\"@g')		#U盘创建分区时的ID
			serial=$(echo "${line}" | grep -Po ' SERIAL="+\K[^" ]+' | sed -n '1p' | sed 's@\\@\\\\@g' | sed 's@\"@\\\"@g')		#U盘出厂序列号
			vendor=$(echo "${line}" | grep -Po ' VENDOR="+\K[^" ]+' | sed -n '1p' | sed 's@\\@\\\\@g' | sed 's@\"@\\\"@g')		#U盘品牌名称
			model=$(echo "${line}" | grep -Po ' MODEL="+\K[^" ]+' | sed -n '1p' | sed 's|_| |' | sed 's@\\@\\\\@g' | sed 's@\"@\\\"@g')		#U盘名称

			mountpoint=$(echo "${line}" | grep -Po ' MOUNTPOINT="+\K[^" ]+' | sed -n '$p')		#U盘挂载点
			if [[ -n ${mountpoint} ]]; then		#这个是适配没分区整个U盘挂载的情况
				index="0"
				vitos_usb_mount_list_details
			fi
		elif [[ -n ${usb_name} ]]; then		#处理分区的信息
			index=$(echo "${line}" | grep -Po ' NAME="+\K[^" ]+' | grep "${usb_name}" | sed -n '1p' | grep -E -o "[0-9]*")
			mountpoint=$(echo "${line}" | grep -Po ' MOUNTPOINT="+\K[^" ]+' | sed -n '$p')
			if [[ -n ${index} ]] && [[ -n ${mountpoint} ]]; then
				vitos_usb_mount_list_details
			fi
		fi
	done
	IFS=$IFS_old

	echo "{\"status\": 0,\"message\": \"\",\"enable_list\": [${enable_list}],\"disable_list\": [${disable_list}]}"
}

#输出分区详细信息
function vitos_usb_mount_list_details(){
	uuid=$(echo "${line}" | grep -Po ' UUID="+\K[^" ]+' | sed -n '1p')		#分区ID
	label1=$(echo "${line}" | grep -Eo '" LABEL=".*" FSSIZE' | sed -n '1p' | sed 's/^" LABEL="//'| sed 's/" FSSIZE$//')		#分区名称,未编码前的
	label=$(python3 "/srv/py/app_str_decode.py" "${label1}" 2>/dev/null | sed 's@\\@\\\\@g' | sed 's@\"@\\\"@g')		#使用python3对中文分区名称转码
	fssize=$(echo "${line}" | grep -Po ' FSSIZE="+\K[^" ]+' | sed -n '1p')		#分区大小

	dir=$(echo "$(ls -l "${MPD_PATH}" 2> /dev/null)" | grep " -> ${mountpoint}$"  | sed -n '1p' | sed "s| -> ${mountpoint}$||")
	if [[ -n ${dir} ]]; then	#获取文件名名称
		dir=$(echo "${dir}" | awk -F " " '{for (i=9;i<=NF;i++)printf("%s ", $i);print ""}' | sed 's| $||')
		path="usb/${dir}"	#给mpd浏览的文件夹路径
	else
		path=""
	fi

	msg="{\"ptuuid\":\"${ptuuid}\",\"serial\":\"${serial}\",\"uuid\":\"${uuid}\",\"model\":\"${vendor} ${model}\",\"label\":\"${label}\",\"fssize\":\"${fssize}\",\"mountpoint\":\"${mountpoint}\",\"index\":\"${index}\",\"path\":\"$(echo ${path} | sed 's@\\@\\\\@g' | sed 's@\"@\\\"@g')\"}"

	if [[ -z "${path}" ]]; then		#mpd音乐文件夹里面没有软链的情况也判断为被禁用
		if [[ -z ${disable_list} ]]; then
			disable_list="${msg}"
		else
			disable_list="${disable_list},${msg}"
		fi
	else
		is_disable=$(grep -En ^"PTUUID=\"${ptuuid}\" SERIAL=\"${serial}\" UUID=\"${uuid}\""$ "${LIST_USB_DISABLE}" 2>/dev/null)
		if [[ -z ${is_disable} ]]; then		#没有被禁用
			if [[ -z ${enable_list} ]]; then
				enable_list="${msg}"
			else
				enable_list="${enable_list},${msg}"
			fi
		else	#被禁用
			if [[ -z ${disable_list} ]]; then
				disable_list="${msg}"
			else
				disable_list="${disable_list},${msg}"
			fi
		fi
	fi
}

# U盘状态改变，设置为 启用 或 禁用
# ${1} 0：禁用；1：启用.
# ${2} U盘信息：ptuuid=??&serial=??&uuid=??
function vitos_usb_state_change(){
	if [[ ! -d "${MPD_PATH}" ]]; then
		mkdir -p "${MPD_PATH}"
	fi
	if [[ ! -d "${SETTING_DIR}" ]]; then
		mkdir -p "${SETTING_DIR}"
	fi
	if [[ -z ${1} ]] || [[ -z ${2} ]]; then
		echo -n "{\"status\":1,\"message\":\"101\"}"
		return 1
	fi
	log="/tmp/log_vitos_usb/usb_state_change.log"
	if [[ ! -e "/tmp/log_vitos_usb/" ]]; then
		mkdir -p "/tmp/log_vitos_usb/"
	fi
	echo "请求的内容：${2}" > "${log}"
	alias urldecode='sed "s@+@ @g;s@%@\\\\x@g" | xargs -0 printf "%b"'
	mountpoint=$(echo "${2}" | grep -Po 'mountpoint[=]+\K[^&]+' | urldecode | sed -n '1p')
	if [[ -z ${mountpoint} ]]; then
		echo -n "{\"status\":1,\"message\":\"102\"}"
		return 1
	fi
	ptuuid=$(echo "${2}" | grep -Po 'ptuuid[=]+\K[^&]+' | urldecode | sed -n '1p')
	serial=$(echo "${2}" | grep -Po 'serial[=]+\K[^&]+' | urldecode | sed -n '1p')
	uuid=$(echo "${2}" | grep -Po '&uuid[=]+\K[^&]+' | urldecode | sed -n '$p')
	if [[ -z ${uuid} ]]; then		#因为部分字符和ptuuid重复，获取方式会出问题，所以增加判断
		uuid=$(echo "${2}" | grep -Po ^'uuid[=]+\K[^&]+' | urldecode | sed -n '$p')
	fi
	if [[ -z ${ptuuid} ]] && [[ -z ${serial} ]] && [[ -z ${uuid} ]] ; then		#请求的U盘ID、U盘序号、分区ID必须有一个不为空
		echo -n "{\"status\":1,\"message\":\"103\"}"
		return 1
	fi

	info="PTUUID=\"${ptuuid}\" SERIAL=\"${serial}\" UUID=\"${uuid}\""
	echo "要匹配的内容：${info}" >> "${log}"
	if [[ 0 = "${1}" ]]; then	#禁用
		if [[ -z $(grep -En ^"${info}"$ "${LIST_USB_DISABLE}" 2>/dev/null) ]]; then
			echo "${info}" >> "${LIST_USB_DISABLE}"
			echo "配置表写入" >> "${log}"
		fi

		dir=$(echo "$(ls -l "${MPD_PATH}" 2> /dev/null)" | grep " -> ${mountpoint}$"  | sed -n '1p' | sed "s| -> ${mountpoint}$||")
		if [[ -n ${dir} ]]; then
			echo "找到软链指向位置： ${dir}" >> "${log}"
			dir=$(echo "${dir}" | awk -F " " '{for (i=9;i<=NF;i++)printf("%s ", $i);print ""}' | sed 's| $||')
			if [[ -n "${dir}" ]]; then
				folder="${MPD_PATH}${dir}"
				echo "要删除的文件夹： ${folder}" >> "${log}"
				rm -d "${folder}" >> "${log}" 2>&1	#删除软链文件夹
				mpc update "usb/${dir}" >> "${log}" 2>&1
			fi
		fi
	else		#启用
		if [[ -e "${LIST_USB_DISABLE}" ]]; then
			line=$(grep -En ^"${info}"$ "${LIST_USB_DISABLE}" 2>/dev/null | sed -n '1p' | grep -Eo ^"[0-9]+")
			if [[ -n ${line} ]]; then		#有匹配就删除
				echo "配置表删除" >> "${log}"
				sed -i "${line}d" "${LIST_USB_DISABLE}" >> "${log}" 2>&1
			fi
		fi

		label=$(echo "${2}" | grep -Po 'label[=]+\K[^&]+' | urldecode | sed -n '1p')
		if [[ -z ${label} ]]; then
			dir="No Label_$(echo ${uuid:0:8})"
		else
			dir="${label}_$(echo ${uuid:0:8})"
		fi
		folder="${MPD_PATH}/${dir}"
		if [[ -e "${folder}" ]] && [[ -z $(ls -l "${folder}" 2> /dev/null | grep " ${mountpoint}"$) ]]; then
			i=0		#文件夹名称有存在一样的,就递归创建新的文件夹名称
			while [[ true ]]; do
				if [[ ${i} -lt 10 ]]; then
					i2="00${i}"
				elif [[ ${i} -lt 100 ]]; then
					i2="0${i}"
				else
					i2="${i}"
				fi
				folder_path="${folder}_i2"

				if [[ ${i} -gt 10 ]] || [[ ! -d ${folder_path} ]] || [[ -n $(ls -l "${folder_path}" 2> /dev/null | grep " -> ${mountpoint}$") ]]; then
					folder="${folder_path}"
					break
				fi
				i=$((${i} + 1))
			done
		fi

		echo "要创建的文件夹： ${folder}" >> "${log}"
		ln -snf "${mountpoint}" "${folder}" >> "${log}" 2>&1
		mpc update "usb/${dir}" >> "${log}" 2>&1
	fi
	echo -n "{\"status\":0,\"message\":\"${1}\"}"
}

#开机时自动挂载usb设备
function t_usb_boot_run(){
	echo "先清除之前的U盘挂载记录和软链"
	# vitos_usb_auto_remove
	rm "${RECORD_PATH}"*
	rm -d "${MPD_PATH}"*

	echo "为插入的U盘创建软链"
	local IFS_old=$IFS
	IFS=$'\n'
	for line in $(lsblk -P -o tran,name,ptuuid,serial,uuid,label,mountpoint 2>/dev/null); do
		if [[ ${line} =~ ^'TRAN="usb" ' ]]; then		#只处理U盘
			usb_name=$(echo "${line}" | grep -Po ' NAME="+\K[^" ]+' | sed -n '1p')		#类似 sdc
			ptuuid=$(echo "${line}" | grep -Po ' PTUUID="+\K[^" ]+' | sed -n '1p')		#U盘创建分区时的ID
			serial=$(echo "${line}" | grep -Po ' SERIAL="+\K[^" ]+' | sed -n '1p')		#U盘出厂序列号

			t_usb_boot_run_detatils "${usb_name}"
		elif [[ -n ${usb_name} ]]; then		#处理分区的信息
			usb_name_child=$(echo "${line}" | grep -Po ' NAME="+\K[^" ]+' | grep "${usb_name}" | sed -n '1p')
			index=$(echo "${usb_name_child}" | grep -E -o "[0-9]*")
			if [[ -z ${index} ]]; then
				continue
			fi
			uuid=$(echo "${line}" | grep -Po ' UUID="+\K[^" ]+' | sed -n '1p')		#分区ID
			if [[ -z ${uuid} ]]; then
				echo "-- uuid为空的分区 ${usb_name_child} --"
				k=0
				while [[ ${k} -lt 100 ]]; do
					((k++))
					uuid=$(lsblk -no uuid -d /dev/${usb_name_child})
					if [[ -n ${uuid} ]]; then
						ptuuid=$(lsblk -no ptuuid -d /dev/${usb_name})
						serial=$(lsblk -no serial -d /dev/${usb_name})
						echo "循环第${k}次获取到${usb_name_child}的uuid:${uuid}"
						break
					fi
				done
			fi
			t_usb_boot_run_detatils "${usb_name_child}" ${uuid}
		fi
	done
	IFS=$IFS_old

	echo "更新mpd的usb文件夹"
	mpc update "usb"
}

#开机时自动挂载usb设备的分区
function t_usb_boot_run_detatils(){
	if [[ -n ${2} ]]; then
		uuid="${2}"
	else
		uuid=$(echo "${line}" | grep -Po ' UUID="+\K[^" ]+' | sed -n '1p')		#分区ID
		if [[ -z ${uuid} ]]; then
			echo "-- 跳过 uuid为空的 ${1} --"
			return 1
		fi
	fi

	is_disable=$(grep -En ^"PTUUID=\"${ptuuid}\" SERIAL=\"${serial}\" UUID=\"${uuid}\"" "${LIST_USB_DISABLE}" 2>/dev/null)
	if [[ -n ${is_disable} ]]; then
		echo "-- 跳过 被禁用的 ${1} --"
		return 2	#U盘被禁用直接跳过
	fi

	# mountpoint=$(echo "${line}" | grep -Po ' MOUNTPOINT="+\K[^" ]+' | sed -n '$p')		#U盘挂载点
	mountpoint="/media/${1}"		#U盘挂载点
	echo "挂载点为 ${mountpoint}"

	#文件夹名称使用label和uuid前8位
	label1=$(echo "${line}" | grep -Eo '" LABEL=".*" MOUNTPOINT' | sed -n '1p' | sed 's/^" LABEL="//'| sed 's/" MOUNTPOINT$//')		#分区名称,未编码前的
	label=$(python3 "/srv/py/app_str_decode.py" "${label1}" 2>/dev/null)		#使用python3对中文分区名称转码
	if [[ -z ${label} ]]; then
		dir="No Label_$(echo ${uuid:0:8})"
	else
		dir="${label}_$(echo ${uuid:0:8})"
	fi
	folder="${MPD_PATH}${dir}"
	echo "文件夹为 ${folder}"

	if [[ -e "${folder}" ]] && [[ -z $(ls -l "${folder}" 2> /dev/null | grep " ${mountpoint}"$) ]]; then
		i=0		#文件夹名称有存在一样的,就递归创建新的文件夹名称
		while [[ true ]]; do
			echo "文件夹名称查询循环 ${i}"
			if [[ ${i} -lt 10 ]]; then
				i2="00${i}"
			elif [[ ${i} -lt 100 ]]; then
				i2="0${i}"
			else
				i2="${i}"
			fi
			folder_path="${folder}_${i2}"

			if [[ ${i} -gt 10 ]] || [[ ! -d ${folder_path} ]] || [[ -n $(ls -l "${folder_path}" 2> /dev/null | grep " -> ${mountpoint}$") ]]; then
				folder="${folder_path}"
				echo "文件夹修改为 ${folder}"
				break
			fi
			i=$((${i} + 1))
		done
	fi

	ln -snf "${mountpoint}" "${folder}"
	echo "挂载点 ${mountpoint} 创建软链接到 ${folder} 结果 $?"
}

case "${1}" in
	"boot_run" )		#开机运行
		t_usb_boot_run
		;;
	"auto_add" )		#U盘插入时创建软链
		vitos_usb_auto_add "${2}" "${3}" "${4}" "${5}"
		;;
	"auto_remove" )		#U盘拔掉时删除软链
		vitos_usb_auto_remove "${2}"
		;;
	"mount_list" )		#已挂载的U盘
		vitos_usb_mount_list
		;;
	"enable_usb" )		#启用U盘
		vitos_usb_state_change 1 "${2}"
		;;
	"disable_usb" )		#禁用U盘
		vitos_usb_state_change 0 "${2}"
		;;
	* )
		echo -n "{\"status\":98,\"message\":\"987\"}"		#指令错误
		exit 98
		;;
esac
exit $?
