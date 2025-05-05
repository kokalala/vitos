#!/bin/sh

##################################################
### 扫描局域网内的samba服务器、挂载操作	
### Created by wannoo on 2019/12/6
### last modified 2021/01/26
##################################################

MOUNT_PATH="/media/nas/"		#文件夹挂载路径
MPD_PATH="/mnt/mpd/music/nas/"		#mpd的文件夹路径

SMB_lOG_DIR="/tmp/log_vitos_samba/"		#日志文件夹
SMB_MOUNT_lOG="${SMB_lOG_DIR}smb_mount.log"		#mount日志
SMB_UMOUNT_lOG="${SMB_lOG_DIR}smb_umount.log"		#umount日志
SMB_USE_lOG="${SMB_lOG_DIR}use_mount.log"		#软链日志
SMB_USE_QUERY_lOG="${SMB_lOG_DIR}use_query.log"		#软链日志
SMB_USE_RECONNECT_lOG="${SMB_lOG_DIR}use_reconnect.log"		#软链日志

SETTING_DIR="/mnt/settings/"
SMB_MOUNT_RECORD="${SETTING_DIR}vitos_smb_mount_record"		#挂载结果存储位置
SMB_USED_RECORD="${SETTING_DIR}vitos_smb_used_record"		#samba使用记录存储位置
PYTHON_GREP="/srv/py/tool/grep_star.py"		#使用python进行grep

alias urldecode='sed "s@+@ @g;s@%@\\\\x@g" | xargs -0 printf "%b"'		#解码
alias urlencode='tr -d "\n" |od -An -tx1|tr " " %'		#编码

#读取扫描记录并以JSON格式输出
#示例输出: 	{"status":0,"message":"0","scan_list":[
# {"ip":"192.168.10.227","name":"ARCHL","share":["Datttt"]},
# {"ip":"192.168.8.247","name":"JENKINSCHORUS","share":["print$"]}
# ]}
function t_samba_list(){
	IFS_old=$IFS
	IFS=$'\n'

	info=$(nmblookup '*' --debuglevel=0 2>/dev/null | grep -Eo "^([0-9]{1,3}[\.]){3}[0-9]{1,3}")
	rtn=$?

	echo -n "{\"status\":0,\"message\":\"${rtn}\",\"scan_list\":["

	if [[ 0 -eq ${rtn} ]]; then
		i=0
		for ip in ${info}; do
			name=$(nmblookup -A ${ip} --debuglevel=0 2>/dev/null | grep -Eo ".* <00> " | sed -n '1p' | sed 's/^[ \t]*//' | sed 's/[ \t]*<00> $//' | sed 's@\\@\\\\@g' | sed 's@\"@\\\"@g')
			if [[ -z ${name} ]]; then
				continue
			fi
			j=0
			for disk in $(smbclient -L "${ip}" -N --debuglevel=0 -g 2>/dev/null| grep ^"Disk|" | cut -d '|' -f 2);do
				if [[ 0 -ne ${j} ]]; then
					share="${share},\"${disk}\""
				else
					share="\"${disk}\""
					j=1
				fi
			done
			if [[ 0 -ne ${j} ]]; then
				if [[ 0 -ne ${i} ]]; then
					echo -n ","
				else
					i=1
				fi
				echo -n "{\"ip\":\"${ip}\",\"name\":\"${name}\",\"share\":[${share}]}"
			fi
		done
	fi

	echo -n "]}"

	IFS=$IFS_old
}

# 挂载网络存储
# 传入参数示例： ip=192.168.8.31&share=nfs&user=root&password=root
function t_mount_nas(){
	if [[ ! -e "${SMB_lOG_DIR}" ]]; then
		mkdir -p "${SMB_lOG_DIR}"
	fi
	echo -e "\t\t$(date +%s) 挂载开始 mount_nas" > "${SMB_MOUNT_lOG}"
	echo "${1}" >> "${SMB_MOUNT_lOG}"

	if [[ ! -d "${MOUNT_PATH}" ]]; then
		mkdir -p "${MOUNT_PATH}" >> "${SMB_MOUNT_lOG}" 2>&1
	fi
	if [[ ! -d "${MOUNT_PATH}" ]]; then
		echo "101"		#media/nas 文件夹创建失败
		return 1
	fi

	device=$(echo "${1}" | grep -Po 'device[=]+\K[^&]+' | urldecode | sed -n '1p' | sed 's@^smb://@@g' | sed 's@^//@@g' | sed 's@^/@@g')
	if [[ -z ${device} ]]; then
		ip=$(echo "${1}" | grep -Po 'ip[=]+\K[^&]+' | urldecode | sed -n '1p' | grep -E -o "([0-9]{1,3}[\.]){3}[0-9]{1,3}")
		if [[ -z "${ip}" ]]; then
			echo "103"		#ip地址不正确
			return 1
		fi
		share=$(echo "${1}" | grep -Po 'share[=]+\K[^&]+' | urldecode | sed -n '1p')
	else		#如果传上来的不是IP,而是//Z1/Data就通过nmblookup获取IP
		if [[ ! "${device}" =~ .+/+.+ ]]; then
			echo "104"		#传入的服务器地址格式不正确
			return 1
		fi
		host=$(echo ${device%%/*})
		if [[ ${host} =~ ^([0-9]{1,3}[\.]){3}[0-9]{1,3}$ ]]; then
			ip=${host}
			host=""
		else
			ip=$(nmblookup "${host}" --debuglevel=0 2>/dev/null | awk '{print $1}' | grep -E -o "([0-9]{1,3}[\.]){3}[0-9]{1,3}"; test ${PIPESTATUS[0]} -eq 0)
			if [[ $? -ne 0 ]] || [[ -z "${ip}" ]]; then
				echo "103"		#通过主机名获取ip地址失败
				return 1
			fi
		fi
		share=$(echo ${device#*/})
	fi
	if [[ -z ${share} ]]; then
		echo "105"		#没传入 文件夹名称
		return 1
	fi
	if [[ -n $(echo "${share}" | grep "\\\\") ]]; then
		echo "107"		#文件夹名称有特殊字符
		return 1
	fi
	smb="//${ip}/${share}"		#samba服务器ip和要挂载的文件夹路径
	dir="${MOUNT_PATH}${ip}_$(echo "${share}" | sed 's@/@_@g')"		#挂载目录的文件夹完整路径
	echo -e "smb：${smb}\ndir：${dir}" >> "${SMB_MOUNT_lOG}"
	if [[ -n $(mount -t cifs | grep ^"${smb} on ${dir}") ]]; then		#已挂载直接返回文件夹内容
		show=$(t_show_dir "${ip}" "${share}" "" "2")
		show_rtn=$?
		if [[ 0 -eq ${show_rtn} ]]; then
			echo "${show}"
			echo "已挂载直接返回文件夹内容" >> "${SMB_MOUNT_lOG}" 
			return 0
		fi
		echo "没办法显示文件夹内容，先卸载再重新挂载" >> "${SMB_MOUNT_lOG}" 
		umount "${dir}" >> "${SMB_MOUNT_lOG}" 2>&1
		rm -d "${dir}" >> "${SMB_MOUNT_lOG}" 2>&1
	fi

	is_create_dir=0
	if [[ ! -d "{dir}" ]]; then		#创建文件夹
		mkdir -p "${dir}" >> "${SMB_MOUNT_lOG}" 2>&1
		is_create_dir=1
	fi

	#获取密码并解密
	psd=""
	password=$(echo "${1}" | grep -Po 'password[=]+\K[^&]+' | urldecode | sed -n '1p')
	if [[ -n "${password}" ]]; then
		psd=$(thunder_aes_cbc128 "${password}")		#密码解析
		if [[ -z "${psd}" ]]; then
			echo -e "password：${password}" >> "${SMB_MOUNT_lOG}"
			echo "106"
			return 1
		fi
	fi
	#获取用户名并挂载
	user=$(echo "${1}" | grep -Po 'user[=]+\K[^&]+' | urldecode | sed -n '1p')
	if [[ -n "${user}" ]]; then
		echo -e "user${user}\npassword：${password}" >> "${SMB_MOUNT_lOG}"
		mount_info=$(mount -t cifs -v "${smb}" "${dir}" -o username="${user}",password="${psd}",iocharset=utf8 2>&1)
		mount_rtn=$?
	else
		mount_info=$(mount -t cifs -v "${smb}" "${dir}" -o password="${psd}",iocharset=utf8 2>&1)
		mount_rtn=$?
	fi
	if [[ ${mount_rtn} -ne 0  ]]; then
		if [[ -n "${user}" ]]; then
			mount_info=$(mount -t cifs -v "${smb}" "${dir}" -o username="${user}",password="${psd}",iocharset=utf8,vers=2.0 2>&1)
			mount_rtn=$?
		else
			mount_info=$(mount -t cifs -v "${smb}" "${dir}" -o password="${psd}",iocharset=utf8,vers=2.0 2>&1)
			mount_rtn=$?
		fi
	fi
	if [[ ${mount_rtn} -ne 0  ]]; then
		if [[ -n "${user}" ]]; then
			mount_info=$(mount -t cifs -v "${smb}" "${dir}" -o username="${user}",password="${psd}",iocharset=utf8,vers=1.0 2>&1)
			mount_rtn=$?
		else
			mount_info=$(mount -t cifs -v "${smb}" "${dir}" -o password="${psd}",iocharset=utf8,vers=1.0 2>&1)
			mount_rtn=$?
		fi
	fi

	#处理挂载结果
	if [[ ${mount_rtn} -eq 0 ]]; then		#挂载成功
		mount_record="{\"ip\":\"${ip}\",\"share\":\"${share}\",\"query\":\""
		t_insert "${mount_record}" "${1}" >> "${SMB_MOUNT_lOG}"

		t_show_dir "${ip}" "${share}" "" "1"	#输出文件夹列表
		echo -e "\t\t$(date +%s) \n${smb}挂载到${dir}成功" >> "${SMB_MOUNT_lOG}"
	else		#挂载失败
		if [[ "${mount_info}" =~ "mount error(13): Permission denied" ]]; then
			echo "301"
		elif [[ "${mount_info}" =~ "mount error(113): could not connect to ${ip}Unable to find suitable address."$ ]]; then
			echo "302"
		elif [[ "${mount_info}" =~ "mount error(2): No such file or directory" ]]; then
			echo "303"
		elif [[ "${mount_info}" =~ "mount error(22): Invalid argument" ]]; then
			echo "304"
		elif [[ "${mount_info}" =~ "mount error(16): Device or resource busy" ]]; then
			echo "305"
		elif [[ "${mount_info}" =~ "${dir}.mount already exists." ]]; then
			echo "306"
		elif [[ "${mount_info}" =~ "Couldn't chdir to ${dir}: No such file or directory"$ ]]; then
			echo "307"
		else
			echo "300"		#挂载失败	
		fi
		echo -e "\t\t$(date +%s) \n${smb}挂载到${dir}失败：${mount_rtn}原因：\n${mount_info}" >> "${SMB_MOUNT_lOG}"
		if [[ 1 -eq ${is_create_dir} ]]; then		#删除创建的文件夹
			rm -d "${dir}" >> "${SMB_MOUNT_lOG}" 2>&1
		fi
	fi
	return ${mount_rtn}
}

#挂载成功后，如果有匹配就替换，没有就将信息追加到存储文件。
function t_insert(){
	echo -e "t_insert : \n\t${1}\n\t${2}"
	if [[ -z "${1}" ]] || [[ -z "${2}" ]]; then
		return 1
	fi
	local all="${1}${2}\"}"
	if [[ -e "${SMB_MOUNT_RECORD}" ]]; then
		line=$(python "${PYTHON_GREP}" "${SMB_MOUNT_RECORD}" "${1}")
		if [[ -n ${line} ]]; then		#有匹配就替换
			echo "替换第 ${line} 行"
			sed -i "${line}c ${all}" "${SMB_MOUNT_RECORD}"
		else
			echo "追加内容"
			echo "${all}" >> "${SMB_MOUNT_RECORD}"
		fi
	else
		parent_dir=$(dirname "${SMB_MOUNT_RECORD}")
		if [[ ! -d "${parent_dir}" ]]; then
			echo "创建文件夹"
			mkdir -p "${parent_dir}"
		fi
		echo "创建记录文件"
		echo "${all}" > "${SMB_MOUNT_RECORD}"
	fi
}

# 卸载网络存储
# 如果有软链正在被使用,就直接结束，不卸载。
# 传入文件夹路径和samba地址	示例:ip=192.168.8.31&share=nfs
function t_umount_nas(){
	ip=$(echo "${1}" | grep -Po 'ip[=]+\K[^&]+' | urldecode | sed -n '1p' | grep -E -o "([0-9]{1,3}[\.]){3}[0-9]{1,3}")
	share=$(echo "${1}" | grep -Po 'share[=]+\K[^&]+' | urldecode | sed -n '1p')
	echo -e "\t\t$(date +%s) 卸载开始 umount_nas\n${1}" > "${SMB_UMOUNT_lOG}"
	if [[ -z ${ip} ]] || [[ -z ${share} ]]; then
		echo -n "202"
		return 1
	fi
	dir="${MOUNT_PATH}${ip}_$(echo "${share}" | sed 's@/@_@g')"
	if [[ ! -d ${dir} ]]; then
		echo -n "203"
		return 1
	fi
	if [[ -n $(ls -l "${MPD_PATH}" 2> /dev/null | grep " -> ${dir}") ]]; then		#如果有软链正在被使用,就直接结束，不卸载。
		echo "1"
		return 0
	fi

	msg=$(umount "${dir}" 2>&1)
	rtn=$?
	echo -e "\t\t$(date +%s) \n$卸载 ${dir} 结果：${rtn} 信息：\n${msg}" >> "${SMB_UMOUNT_lOG}"
	if [[ 0 -eq ${rtn} ]]; then
		rm -d "${dir}" >> "${SMB_UMOUNT_lOG}" 2>&1		#删除空文件夹
		echo "0"
	else
		if [[ ${msg} =~ ^"umount: ${dir}: No such file or directory" ]]; then
			echo "301"
		elif [[ ${msg} =~ ^"umount: ${dir}: must be superuser to unmount." ]]; then
			echo "302"
		elif [[ ${msg} =~ ^"umount: ${dir}: not mounted." ]]; then
			echo "303"
		else
			echo "300"		#卸载失败
		fi
	fi
	t_delete "{\"ip\":\"${ip}\",\"share\":\"${share}\",\"query\":\"" >> "${SMB_UMOUNT_lOG}" 2>&1		#删除记录表第一项匹配
	return ${rtn}
}
#删除记录表第一项匹配
function t_delete(){
	echo "t_delete : ${1}"
	if [[ -z "${1}" ]]; then
		return 1
	fi
	if [[ -e "${SMB_MOUNT_RECORD}" ]]; then
		line=$(python "${PYTHON_GREP}" "${SMB_MOUNT_RECORD}" "${1}")
		if [[ -n ${line} ]]; then		#有匹配就删除
			echo "删除第 ${line} 行"
			sed -i "${line}d" "${SMB_MOUNT_RECORD}"
		fi
	fi
}
# 通过web请求，显示目录里的文件夹列表
# 传入参数示例：ip=192.168.8.31&share=nfs&path=dir/dir/dir
function t_show_dir_by_url(){
	ip=$(echo "${1}" | grep -Po 'ip[=]+\K[^&]+' | urldecode | sed -n '1p' | grep -E -o "([0-9]{1,3}[\.]){3}[0-9]{1,3}")
	share=$(echo "${1}" | grep -Po 'share[=]+\K[^&]+' | urldecode | sed -n '1p')
	if [[ -z ${ip} ]] || [[ -z ${share} ]]; then
		echo -n "{\"status\":1,\"message\":\"201\"}"
		return 1
	fi
	path=$(echo "${1}" | grep -Po 'path[=]+\K[^&]+' | urldecode | sed -n '1p')
	t_show_dir "${ip}" "${share}" "${path}"
}


# 显示目录里的文件夹列表
# ${1}：IP
# ${2}：nas文件夹
# ${3}：文件夹路径
# ${4}：信息：1：刚挂载时查询；2：挂载操作时查询已有文件夹；0：查询请求发出的
function t_show_dir(){
	ip="${1}"
	share="${2}"
	if [[ -z ${ip} ]] || [[ -z ${share} ]]; then
		echo -n "{\"status\":1,\"message\":\"202\"}"
		return 1
	fi
	[ -z "${3}" ] && path="/" || path="${3}"
	[ -z "${4}" ] && msg="0" || msg="${4}"
	dir="${MOUNT_PATH}${ip}_$(echo "${share}" | sed 's@/@_@g')"		#挂载目录的文件夹完整路径
	if [[ ! -d "${dir}" ]]; then
		echo -n "{\"status\":1,\"message\":\"203\"}"
		return 1
	fi
	echo -n "{\"ip\":\"${ip}\",\"share\":\"$(echo "${share}" | sed 's@\\@\\\\@g' | sed 's@\"@\\\"@g')\","
	echo -n "\"path\":\"$(echo ${path} | sed 's@\\@\\\\@g' | sed 's@\"@\\\"@g')\","
	echo -n "\"status\":0,\"message\":\"${msg}\",\"dir\":["
	i=0
	IFS_old=$IFS
	IFS=$'\n'
	for dir_child in $(echo "$(ls -F "${dir}/${path}")" | grep "/"$ |sed 's@/$@@' | sed 's@\\@\\\\@g' | sed 's@\"@\\\"@g'); do
		if [[ 0 -ne ${i} ]]; then
			echo -n ",\"${dir_child}\""
		else
			echo -n "\"${dir_child}\""
			i=1
		fi
	done
	IFS=$IFS_old
	echo "]}"
}

# 创建软链，将文件夹链到mpd目录里
# 提交参数示例：ip=192.168.10.128&share=NAS&folders=d\nc
# ip：samba设备IP
# share：挂载的samba文件夹
# folders：选择的文件夹列表，多个文件夹使用“\n”进行分割，如果文件夹原来的名称里有“\n”，在提交时应提交“\\n”
function t_use_nas(){
	if [[ ! -d "${MPD_PATH}" ]]; then
		mkdir -p "${MPD_PATH}"
	fi
	echo "${1}" > "${SMB_USE_lOG}"
	ip=$(echo "${1}" | grep -Po 'ip[=]+\K[^&]+' | urldecode | sed -n '1p' | grep -E -o "([0-9]{1,3}[\.]){3}[0-9]{1,3}")
	share=$(echo "${1}" | grep -Po 'share[=]+\K[^&]+' | urldecode | sed -n '1p')
	if [[ -z ${ip} ]] || [[ -z ${share} ]]; then
		echo -n "{\"status\":1,\"message\":\"202\"}"
		return 1
	fi
	path_dir="${ip}_$(echo "${share}" | sed 's@/@_@g')"		#挂载位置的根目录
	target_dir="${MOUNT_PATH}${path_dir}"		#挂载位置的根目录
	echo "target_dir：${target_dir}" >> "${SMB_USE_lOG}"
	if [[ ! -d ${target_dir} ]]; then
		echo -n "{\"status\":1,\"message\":\"203\"}"
		return 1
	fi

	folders=$(echo "${1}" | grep -Po 'folders[=]+\K[^&]+' | urldecode | sed -n '1p')
	if [[ -z ${folders} ]] || [[ "/" = "${folders}" ]]; then	#使用的整个根目录
		ln -snf "${target_dir}" "${MPD_PATH}" >> "${SMB_USE_lOG}" 2>&1

		record="{\"ip\":\"${ip}\",\"share\":\"${share}\",\"folder\":\"\",\"path\":\"nas/${path_dir}\",\"state\":\""
		t_nas_insert "${record}" "1\"}" >> "${SMB_USE_lOG}" 2>&1

		echo -n "{\"status\":0,\"message\":\"1\"}"

		mpc update "nas/${path_dir}" >> "${SMB_USE_lOG}" 2>&1		#mpd更新数据
	else
		link_dir="${MPD_PATH}${path_dir}"		#软链接的目录
		folders=$(echo -e "${folders}")
		IFS_old=$IFS
		IFS=$'\n'
		for folder in ${folders}; do		#获取全部目录路径
			if [[ -z $(echo ${folder} | grep ^"/") ]]; then
				folder="/${folder}"
			fi
			echo "folder : ${folder}" >> "${SMB_USE_lOG}"
			folder_dir=$(echo ${folder} | sed 's@/@_@g')
			ln -snf "${target_dir}${folder}" "${link_dir}${folder_dir}" >> "${SMB_USE_lOG}" 2>&1
			
			record="{\"ip\":\"${ip}\",\"share\":\"${share}\",\"folder\":\"${folder}\",\"path\":\"nas/${path_dir}${folder_dir}\",\"state\":\""
			t_nas_insert "${record}" "1\"}" >> "${SMB_USE_lOG}" 2>&1

			mpc update "nas/${path_dir}${folder_dir}" >> "${SMB_USE_lOG}" 2>&1		#mpd更新数据
		done
		IFS=$IFS_old
		echo -n "{\"status\":0,\"message\":\"2\"}"
	fi

}

#删除软链，停止文件夹使用
function t_remove_nas(){
	ip=$(echo "${1}" | grep -Po 'ip[=]+\K[^&]+' | urldecode | sed -n '1p' | grep -E -o "([0-9]{1,3}[\.]){3}[0-9]{1,3}")
	share=$(echo "${1}" | grep -Po 'share[=]+\K[^&]+' | urldecode | sed -n '1p')
	folder=$(echo "${1}" | grep -Po 'folder[=]+\K[^&]+' | urldecode | sed -n '1p')
	if [[ -z ${ip} ]] || [[ -z ${share} ]]; then
		echo -n "{\"status\":1,\"message\":\"202\"}"
		return 1
	fi
	echo -e "remove_nas\n${1}" > "${SMB_USE_lOG}"

	if [[ -z ${folder} ]] || [[ "/" = "${folder}" ]]; then	#挂载的整个根目录
		link_dir="${ip}_$(echo "${share}" | sed 's@/@_@g')"
	else
		link_dir="${ip}_$(echo "${share}" | sed 's@/@_@g')$(echo ${folder} | sed 's@/@_@g')"		#软链接的目录
	fi
	rm -d "${MPD_PATH}${link_dir}" >> "${SMB_USE_lOG}" 2>&1

	record="{\"ip\":\"${ip}\",\"share\":\"${share}\",\"folder\":\"${folder}\",\"path\":\""
	t_nas_delete "${record}" >> "${SMB_USE_lOG}" 2>&1

	dir="${MOUNT_PATH}${ip}_$(echo "${share}" | sed 's@/@_@g')"		#如果没有被使用的软链就卸载samba
	if [[ -d ${dir} ]] && [[ -z $(ls -l "${MPD_PATH}" 2> /dev/null | grep " -> ${dir}") ]]; then
		umount "${dir}" >> "${SMB_USE_lOG}" 2>&1
		t_delete "{\"ip\":\"${ip}\",\"share\":\"${share}\",\"query\":\"" >> "${SMB_UMOUNT_lOG}" 2>&1
	fi

	echo -n "{\"status\":0,\"message\":\"0\"}"

	# mpc update "nas/${link_dir}" >> "${SMB_USE_lOG}" 2>&1 2>&1		#mpd更新数据 #mpd设置文件夹检测，无需执行
}

# 已设置使用的samba文件夹
# state：0：禁用；1：启用且正常使用;2：没挂载;3:密码解密失败;4:smbclient查询失败;5:mpd里面的这个文件夹不存在;6:media里面的这个文件夹不存在
function t_used_list(){
	if [[ ! -e "${SMB_lOG_DIR}" ]]; then
		mkdir -p "${SMB_lOG_DIR}"
	fi
	if [[ ! -e "${SMB_USED_RECORD}" ]]; then
		echo "没有记录的文件" > "${SMB_USE_QUERY_lOG}"
		echo "{\"status\": 0,\"message\": \"101\",\"used_list\": []}"
		return 0
	fi
	echo "{\"status\": 0,\"message\": \"0\",\"used_list\": ["

	local i=0
	local IFS_old=$IFS
	IFS=$'\n'

 	echo "开始查询 $(date +%s)" > "${SMB_USE_QUERY_lOG}"
 	old_ip=""
 	old_share=""
	for line in $(sort "${SMB_USED_RECORD}" 2>/dev/null);do
		if [[ ! "${line}" =~ ^"{\"ip\":\"" ]]; then
			continue
		fi
		ip=$(echo "${line}" | grep -Po 'ip[":]+\K[^"]+' | sed -n '1p')
		share=""
		if [[ -z $(echo "${line}" | grep "\",\"share\":\"\",\"folder\":\"") ]]; then
			share=$(echo "${line}" | grep -Po 'share[":]+\K[^"]+' | sed -n '1p')
		fi
		folder=""
		if [[ -z $(echo "${line}" | grep "\",\"folder\":\"\",\"path\":\"") ]]; then
			folder=$(echo "${line}" | grep -Po 'folder[":]+\K[^"]+' | sed -n '1p')
		fi
		echo -e "\t--ip:${ip}--\n\t--share:${share}--\n\t--folder:${folder}--" >> "${SMB_USE_QUERY_lOG}"
		if [[ -z ${ip} ]] || [[ -z ${share} ]]; then
			state=0
			continue
		fi
		if [[ 0 -eq ${i} ]]; then
			i=1
		else	
			echo -n ","
		fi
		if [[ "0" = $(echo "${line}" | grep -Po 'state[" :]+\K[^"]+') ]]; then	#禁用状态直接返回
			echo "状态0 禁用状态直接返回" >> "${SMB_USE_QUERY_lOG}"
			echo -n "${line}" | sed 's@\\@\\\\@g'
			continue
		fi

		if [[ "${ip}" = "${old_ip}" ]] && [[ "${share}" = "${old_share}" ]]; then
			if [[ "2" = ${state} ]] || [[ "3" = ${state} ]] || [[ "4" = ${state} ]]; then
				echo "跟随上一行状态${state}" >> "${SMB_USE_QUERY_lOG}"
				echo "${line:0:$(echo ${#line}-3)}${state}\"}" | sed 's@\\@\\\\@g'
				continue
			fi
		fi
		
		if [[ "${ip}" != "${old_ip}" ]] || [[ "${share}" != "${old_share}" ]]; then
			echo "需要查询连接状态" >> "${SMB_USE_QUERY_lOG}"
			old_ip=${ip}
			old_share=${share}

			if [[ -z $(mount -t cifs | grep ^"//${ip}/${share} on /media/nas/${ip}_.*") ]]; then
				echo "状态2 没有挂载" >> "${SMB_USE_QUERY_lOG}"
				state=2
				echo "${line:0:$(echo ${#line}-3)}${state}\"}" | sed 's@\\@\\\\@g'
				continue
			fi

			query=$(cat "${SMB_MOUNT_RECORD}" |grep ^"{\"ip\":\"${ip}\",\"share\":\"${share}\",\"query\":\".*" | grep -Po 'query[" :]+\K[^"]+')
			psd=""	#解密后的密码
			password=$(echo "${query}" | grep -Po 'password[=]+\K[^&]+' | urldecode | sed -n '1p')
			if [[ -n "${password}" ]]; then
				psd=$(thunder_aes_cbc128 "${password}")		#密码解析
				if [[ -z "${psd}" ]]; then
					echo "状态3 密码解密失败" >> "${SMB_USE_QUERY_lOG}"
					state=3
					echo "${line:0:$(echo ${#line}-3)}${state}\"}" | sed 's@\\@\\\\@g'
					continue
				fi
			fi

			user=$(echo "${query}" | grep -Po 'user[=]+\K[^&]+' | urldecode | sed -n '1p')
			if [[ -n "${user}" ]]; then
				smbclient -c "exit" "//${ip}/$(echo ${share%%/*})" -U "${user}%${psd}" >> "${SMB_USE_QUERY_lOG}" 2>&1
				rtn=$?
			else
				smbclient -c "exit" "//${ip}/$(echo ${share%%/*})" -N >> "${SMB_USE_QUERY_lOG}" 2>&1
				rtn=$?
			fi
			if [[ 0 -ne ${rtn} ]]; then
				echo "状态4 连接错误" >> "${SMB_USE_QUERY_lOG}"
				state=4
				echo "${line:0:$(echo ${#line}-3)}${state}\"}" | sed 's@\\@\\\\@g'
				continue
			fi
		fi

		path1="${MOUNT_PATH}${ip}_$(echo "${share}" | sed 's@/@_@g')${folder}"
		if [[ -d "${path1}" ]]; then
			path2="${MPD_PATH}${ip}_$(echo "${share}" | sed 's@/@_@g')$(echo ${folder} | sed 's@/@_@g')"
			if [[ -d "${path2}" ]]; then
				echo "状态1 文件夹：${path2}" >> "${SMB_USE_QUERY_lOG}"
				state=1		#启用且连接直接返回
				echo -n "${line}" | sed 's@\\@\\\\@g'
				continue
			else
				echo "状态5 文件夹：${path2}" >> "${SMB_USE_QUERY_lOG}"
				state=5
			fi
		else
			echo "状态6 文件夹：${path1}" >> "${SMB_USE_QUERY_lOG}"
			state=6
		fi
		echo "${line:0:$(echo ${#line}-3)}${state}\"}" | sed 's@\\@\\\\@g'
	done

	IFS=$IFS_old

	echo "]}"

 	echo "结束查询 $(date +%s)" >> "${SMB_USE_QUERY_lOG}"
}

# 已设置使用的samba文件夹，不获取状态
# state：-1，状态未获取
function t_used_list_light(){
	if [[ ! -e "${SMB_lOG_DIR}" ]]; then
		mkdir -p "${SMB_lOG_DIR}"
	fi
	if [[ ! -e "${SMB_USED_RECORD}" ]]; then
		echo "没有记录的文件" > "${SMB_USE_QUERY_lOG}"
		echo "{\"status\": 0,\"message\": \"101\",\"used_list\": []}"
		return 0
	fi
	echo "{\"status\": 0,\"message\": \"0\",\"used_list\": ["

	local i=0
	local IFS_old=$IFS
	IFS=$'\n'

 	echo "开始查询 $(date +%s) 只获取列表" > "${SMB_USE_QUERY_lOG}"
	for line in $(sort "${SMB_USED_RECORD}" 2>/dev/null);do
		if [[ ! "${line}" =~ ^"{\"ip\":\"" ]]; then
			continue
		fi
		ip=$(echo "${line}" | grep -Po 'ip[" :]+\K[^"]+' | sed -n '1p')
		share=$(echo "${line}" | grep -Po 'share[" :]+\K[^"]+' | sed -n '1p')
		echo -e "\t--ip:${ip}--\n\t--share:${share}--" >> "${SMB_USE_QUERY_lOG}"
		if [[ -z ${ip} ]] || [[ -z ${share} ]]; then
			continue
		fi
		if [[ 0 -eq ${i} ]]; then
			i=1
		else	
			echo -n ","
		fi
		state=$(echo "${line}" | grep -Po 'state[" :]+\K[^"]+')
		if [[ "0" = ${state} ]]; then	#禁用状态直接返回
			echo "状态0 禁用状态直接返回" >> "${SMB_USE_QUERY_lOG}"
			echo -n "${line}"
			continue
		fi
		echo "${line:0:$(echo ${#line}-3)}-1\"}"
	done

	IFS=$IFS_old

	echo "]}"

 	echo "结束查询 $(date +%s)" >> "${SMB_USE_QUERY_lOG}"
}

# 查询已设置使用的samba文件夹的状态
# state：0：禁用；1：启用且正常使用;2：没挂载;3:密码解密失败;4:smbclient查询失败;5:mpd里面的这个文件夹不存在;6:media里面的这个文件夹不存在
function t_used_item_status(){
	ip=$(echo "${1}" | grep -Po 'ip[=]+\K[^&]+' | urldecode | sed -n '1p' | grep -E -o "([0-9]{1,3}[\.]){3}[0-9]{1,3}")
	share=$(echo "${1}" | grep -Po 'share[=]+\K[^&]+' | urldecode | sed -n '1p')
	folder=$(echo "${1}" | grep -Po 'folder[=]+\K[^&]+' | urldecode | sed -n '1p')

	if [[ -z ${ip} ]] || [[ -z ${share} ]]; then
		echo -n "{\"status\":1,\"message\":\"202\"}"
		return 1
	fi

	if [[ -z $(mount -t cifs | grep ^"//${ip}/${share} on /media/nas/${ip}_.*") ]]; then
		# echo "状态2 没有挂载" >> "${SMB_USE_QUERY_lOG}"
		echo -n "{\"status\":0,\"message\":\"2\"}"
		return 0
	fi

	query=$(cat "${SMB_MOUNT_RECORD}" |grep ^"{\"ip\":\"${ip}\",\"share\":\"${share}\",\"query\":\".*" | grep -Po 'query[" :]+\K[^"]+')
	psd=""	#解密后的密码
	password=$(echo "${query}" | grep -Po 'password[=]+\K[^&]+' | urldecode | sed -n '1p')
	if [[ -n "${password}" ]]; then
		psd=$(thunder_aes_cbc128 "${password}")		#密码解析
		if [[ -z "${psd}" ]]; then
			# echo "状态3 密码解密失败" >> "${SMB_USE_QUERY_lOG}"
			echo -n "{\"status\":0,\"message\":\"3\"}"
			return 0
		fi
	fi

	user=$(echo "${query}" | grep -Po 'user[=]+\K[^&]+' | urldecode | sed -n '1p')
	if [[ -n "${user}" ]]; then
		smbclient -c "exit" "//${ip}/$(echo ${share%%/*})" -U "${user}%${psd}" >> "${SMB_USE_QUERY_lOG}" 2>&1
		rtn=$?
	else
		smbclient -c "exit" "//${ip}/$(echo ${share%%/*})" -N >> "${SMB_USE_QUERY_lOG}" 2>&1
		rtn=$?
	fi
	if [[ 0 -ne ${rtn} ]]; then
		# echo "状态4 连接错误" >> "${SMB_USE_QUERY_lOG}"
		echo -n "{\"status\":0,\"message\":\"4\"}"
		return 0
	fi

	path1="${MOUNT_PATH}${ip}_$(echo "${share}" | sed 's@/@_@g')${folder}"
	if [[ -d "${path1}" ]]; then
		path2="${MPD_PATH}${ip}_$(echo "${share}" | sed 's@/@_@g')$(echo ${folder} | sed 's@/@_@g')"
		if [[ -d "${path2}" ]]; then
			# echo "状态1 启用且连接直接返回" >> "${SMB_USE_QUERY_lOG}"
			state=1		#启用且连接直接返回
		else
			# echo "状态5 文件夹：${path2}" >> "${SMB_USE_QUERY_lOG}"
			state=5
		fi
	else
		# echo "状态6 文件夹：${path1}" >> "${SMB_USE_QUERY_lOG}"
		state=6
	fi
	echo -n "{\"status\":0,\"message\":\"${state}\"}"
	return 0
}

# 查询已设置使用的samba文件夹的状态
# 忽略samba连线查询
# state：0：禁用；1：启用且正常使用;2：没挂载;3:密码解密失败;4:smbclient查询失败;5:mpd里面的这个文件夹不存在;6:media里面的这个文件夹不存在
function t_used_item_status_ignore_smbclient(){
	ip=$(echo "${1}" | grep -Po 'ip[=]+\K[^&]+' | urldecode | sed -n '1p' | grep -E -o "([0-9]{1,3}[\.]){3}[0-9]{1,3}")
	share=$(echo "${1}" | grep -Po 'share[=]+\K[^&]+' | urldecode | sed -n '1p')
	folder=$(echo "${1}" | grep -Po 'folder[=]+\K[^&]+' | urldecode | sed -n '1p')

	if [[ -z ${ip} ]] || [[ -z ${share} ]]; then
		echo -n "{\"status\":1,\"message\":\"202\"}"
		return 1
	fi

	if [[ -z $(mount -t cifs | grep ^"//${ip}/${share} on /media/nas/${ip}_.*") ]]; then
		# echo "状态2 没有挂载" >> "${SMB_USE_QUERY_lOG}"
		echo -n "{\"status\":0,\"message\":\"2\"}"
		return 0
	fi

	path1="${MOUNT_PATH}${ip}_$(echo "${share}" | sed 's@/@_@g')${folder}"
	if [[ -d "${path1}" ]]; then
		path2="${MPD_PATH}${ip}_$(echo "${share}" | sed 's@/@_@g')$(echo ${folder} | sed 's@/@_@g')"
		if [[ -d "${path2}" ]]; then
			# echo "状态1 启用且连接直接返回" >> "${SMB_USE_QUERY_lOG}"
			state=1		#启用且连接直接返回
		else
			# echo "状态5 文件夹：${path2}" >> "${SMB_USE_QUERY_lOG}"
			state=5
		fi
	else
		# echo "状态6 文件夹：${path1}" >> "${SMB_USE_QUERY_lOG}"
		state=6
	fi
	echo -n "{\"status\":0,\"message\":\"${state}\"}"
	return 0
}

#启用文件夹
function t_enable_nas(){
	ip=$(echo "${1}" | grep -Po 'ip[=]+\K[^&]+' | urldecode | sed -n '1p' | grep -E -o "([0-9]{1,3}[\.]){3}[0-9]{1,3}")
	share=$(echo "${1}" | grep -Po 'share[=]+\K[^&]+' | urldecode | sed -n '1p')
	folder=$(echo "${1}" | grep -Po 'folder[=]+\K[^&]+' | urldecode | sed -n '1p')
	if [[ -z ${ip} ]] || [[ -z ${share} ]]; then
		echo -n "{\"status\":1,\"message\":\"202\"}"
		return 1
	fi
	echo -e "enable_nas\n${1}" > "${SMB_USE_lOG}"

	target_dir="${MOUNT_PATH}${ip}_$(echo "${share}" | sed 's@/@_@g')"		#挂载位置的根目录
	if [[ -z ${folder} ]] || [[ "/" = "${folder}" ]]; then	#挂载整个根目录
		link_dir="${MPD_PATH}"
	else
		link_dir="${MPD_PATH}${ip}_$(echo "${share}" | sed 's@/@_@g')"		#软链接的目录
	fi
	ln -snf "${target_dir}${folder}" "${link_dir}$(echo "${folder}" | sed 's@/@_@g')" >> "${SMB_USE_lOG}" 2>&1

	record="{\"ip\":\"${ip}\",\"share\":\"${share}\",\"folder\":\"${folder}\",\"path\":\""
	t_nas_state_change "${record}" "1" >> "${SMB_USE_lOG}" 2>&1
	echo -n "{\"status\":0,\"message\":\"1\"}"
}

#禁用文件夹
function t_disable_nas(){
	if [[ ! -e /tmp/vitos_tmpdir ]]; then
		mkdir /tmp/vitos_tmpdir
	fi
	ip=$(echo "${1}" | grep -Po 'ip[=]+\K[^&]+' | urldecode | sed -n '1p' | grep -E -o "([0-9]{1,3}[\.]){3}[0-9]{1,3}")
	share=$(echo "${1}" | grep -Po 'share[=]+\K[^&]+' | urldecode | sed -n '1p')
	folder=$(echo "${1}" | grep -Po 'folder[=]+\K[^&]+' | urldecode | sed -n '1p')
	if [[ -z ${ip} ]] || [[ -z ${share} ]]; then
		echo -n "{\"status\":1,\"message\":\"202\"}"
		return 1
	fi
	echo -e "disable_nas\n${1}" > "${SMB_USE_lOG}"

	link_dir="${MPD_PATH}${ip}_$(echo "${share}" | sed 's@/@_@g')"		#软链接的目录
	if [[ -n ${folder} ]] && [[ "/" != "${folder}" ]]; then	#不是整个根目录
		link_dir="${link_dir}$(echo ${folder} | sed 's@/@_@g')"
	fi
	rm -d "${link_dir}" >> "${SMB_USE_lOG}" 2>&1
	ln -snf "/tmp/vitos_tmpdir" "${link_dir}" >> "${SMB_USE_lOG}" 2>&1

	record="{\"ip\":\"${ip}\",\"share\":\"${share}\",\"folder\":\"${folder}\",\"path\":\""
	t_nas_state_change "${record}" "0" >> "${SMB_USE_lOG}" 2>&1
	echo -n "{\"status\":0,\"message\":\"0\"}"
}

# 已断线的文件夹重连
# state：0：禁用；1：启用且正常使用;2：没挂载;3:密码解密失败;4:smbclient查询失败;5:mpd里面的这个文件夹不存在;6:media里面的这个文件夹不存在
# 
function t_reconnect_nas(){
	if [[ ! -e "${SMB_lOG_DIR}" ]]; then
		mkdir -p "${SMB_lOG_DIR}"
	fi
	echo -e "\t\t$(date +%s) 断线重连开始 reconnect_nas\n${1}" > "${SMB_USE_RECONNECT_lOG}"

	if [[ ! -d "${MOUNT_PATH}" ]]; then
		mkdir -p "${MOUNT_PATH}" >> "${SMB_USE_RECONNECT_lOG}" 2>&1
	fi
	if [[ ! -d "${MOUNT_PATH}" ]]; then
		echo "101"		#media/nas 文件夹创建失败
		return 1
	fi
	ip=$(echo "${1}" | grep -Po 'ip[=]+\K[^&]+' | urldecode | sed -n '1p' | grep -E -o "([0-9]{1,3}[\.]){3}[0-9]{1,3}")
	if [[ -z "${ip}" ]]; then
		echo "103"		#通过主机名获取ip地址失败
		return 1
	fi
	share=$(echo "${1}" | grep -Po 'share[=]+\K[^&]+' | urldecode | sed -n '1p')
	if [[ -z ${share} ]]; then
		echo "105"		#没传入 文件夹名称
		return 1
	fi

	smb="//${ip}/${share}"		#samba服务器ip和要挂载的文件夹路径
	dir="${MOUNT_PATH}${ip}_$(echo "${share}" | sed 's@/@_@g')"		#挂载目录的文件夹完整路径

	umount "${smb}" >> "${SMB_USE_RECONNECT_lOG}" 2>&1
	rm -d "${dir}" >> "${SMB_USE_RECONNECT_lOG}" 2>&1

	if [[ ! -d "{dir}" ]]; then		#创建文件夹
		mkdir -p "${dir}" >> "${SMB_USE_RECONNECT_lOG}" 2>&1
	fi
	echo -e "smb：${smb}\ndir：${dir}" >> "${SMB_USE_RECONNECT_lOG}"

	query=$(cat "${SMB_MOUNT_RECORD}" |grep ^"{\"ip\":\"${ip}\",\"share\":\"${share}\",\"query\":\".*" | grep -Po 'query[" :]+\K[^"]+')
	echo "从存储获取到的请求信息:${query}" >> "${SMB_USE_RECONNECT_lOG}"
	psd=""	#解密后的密码
	password=$(echo "${query}" | grep -Po 'password[=]+\K[^&]+' | urldecode | sed -n '1p')
	if [[ -n "${password}" ]]; then
		psd=$(thunder_aes_cbc128 "${password}")		#密码解析
		if [[ -z "${psd}" ]]; then
			echo "106"		#密码解密失败
			return 1
		fi
	fi
	#获取用户名并挂载
	user=$(echo "${query}" | grep -Po 'user[=]+\K[^&]+' | urldecode | sed -n '1p')
	if [[ -n "${user}" ]]; then
		echo -e "user${user}\npassword：${password}" >> "${SMB_USE_RECONNECT_lOG}"
		mount_info=$(mount -t cifs -v "${smb}" "${dir}" -o username="${user}",password="${psd}",iocharset=utf8 2>&1)
		mount_rtn=$?
	else
		mount_info=$(mount -t cifs -v "${smb}" "${dir}" -o password="${psd}",iocharset=utf8 2>&1)
		mount_rtn=$?
	fi
	if [[ ${mount_rtn} -ne 0  ]]; then
		if [[ -n "${user}" ]]; then
			mount_info=$(mount -t cifs -v "${smb}" "${dir}" -o username="${user}",password="${psd}",iocharset=utf8,vers=2.0 2>&1)
			mount_rtn=$?
		else
			mount_info=$(mount -t cifs -v "${smb}" "${dir}" -o password="${psd}",iocharset=utf8,vers=2.0 2>&1)
			mount_rtn=$?
		fi
	fi
	if [[ ${mount_rtn} -ne 0  ]]; then
		if [[ -n "${user}" ]]; then
			mount_info=$(mount -t cifs -v "${smb}" "${dir}" -o username="${user}",password="${psd}",iocharset=utf8,vers=1.0 2>&1)
			mount_rtn=$?
		else
			mount_info=$(mount -t cifs -v "${smb}" "${dir}" -o password="${psd}",iocharset=utf8,vers=1.0 2>&1)
			mount_rtn=$?
		fi
	fi

	#处理挂载结果
	if [[ ${mount_rtn} -eq 0 ]]; then		#挂载成功
		echo -e "\t\t$(date +%s) \n${smb}挂载到${dir}成功" >> "${SMB_USE_RECONNECT_lOG}"

		folder=$(echo "${1}" | grep -Po 'folder[=]+\K[^&]+' | urldecode | sed -n '1p')
		if [[ -z ${folder} ]] || [[ "/" = "${folder}" ]]; then	#挂载整个根目录
			link_dir="${MPD_PATH}${ip}_$(echo "${share}" | sed 's@/@_@g')"
		else
			folder_dir=$(echo ${folder} | sed 's@/@_@g')
			link_dir="${MPD_PATH}${ip}_$(echo "${share}" | sed 's@/@_@g')${folder_dir}"		#软链接的目录
		fi
		if [[ -d "${link_dir}" ]]; then
			echo -e "文件夹存在，直接返回重连接成功" >> "${SMB_USE_RECONNECT_lOG}"
			echo "1"
			return 0
		fi
		target_dir="${MOUNT_PATH}${ip}_$(echo "${share}" | sed 's@/@_@g')"		#挂载位置的根目录
		if [[ -z ${folder} ]] || [[ "/" = "${folder}" ]]; then	#挂载整个根目录
			link_path="${MPD_PATH}"
			rtn=$?
		else
			target_dir="${target_dir}${folder}"
			link_path="${link_dir}"
		fi
		echo -e "文件夹不存在，创建软链" >> "${SMB_USE_RECONNECT_lOG}"
		ln -snf "${target_dir}" "${link_path}" >> "${SMB_USE_RECONNECT_lOG}" 2>&1
		rtn=$?
		if [[ 0 -eq ${rtn} ]]; then
			echo -e "软链创建成功" >> "${SMB_USE_RECONNECT_lOG}"
			if [[ -d "${link_dir}" ]]; then
				echo -e "文件夹存在" >> "${SMB_USE_RECONNECT_lOG}"
				echo "2"
				return 0
			else
				echo -e "文件夹不存在" >> "${SMB_USE_RECONNECT_lOG}"
				echo "201"
			fi
		else
			echo -e "软链创建失败" >> "${SMB_USE_RECONNECT_lOG}"
			echo "203"
		fi
		return 1
	else		#挂载失败
		if [[ "${mount_info}" =~ "mount error(13): Permission denied" ]]; then
			echo "301"
		elif [[ "${mount_info}" =~ "mount error(113): could not connect to ${ip}Unable to find suitable address."$ ]]; then
			echo "302"
		elif [[ "${mount_info}" =~ "mount error(2): No such file or directory" ]]; then
			echo "303"
		elif [[ "${mount_info}" =~ "mount error(22): Invalid argument" ]]; then
			echo "304"
		elif [[ "${mount_info}" =~ "mount error(16): Device or resource busy" ]]; then
			echo -e "重新连接时遇到提示已挂载的情况再查询一下文件夹是否存在" >> "${SMB_USE_RECONNECT_lOG}"

			folder=$(echo "${1}" | grep -Po 'folder[=]+\K[^&]+' | urldecode | sed -n '1p')
			if [[ -z ${folder} ]] || [[ "/" = "${folder}" ]]; then	#挂载整个根目录
				link_dir="${MPD_PATH}${ip}_$(echo "${share}" | sed 's@/@_@g')"
			else
				folder_dir=$(echo ${folder} | sed 's@/@_@g')
				link_dir="${MPD_PATH}${ip}_$(echo "${share}" | sed 's@/@_@g')${folder_dir}"		#软链接的目录
			fi
			if [[ -d "${link_dir}" ]]; then
				echo -e "文件夹存在，直接返回重连接成功" >> "${SMB_USE_RECONNECT_lOG}"
				echo "1"
				return 0
			fi
			target_dir="${MOUNT_PATH}${ip}_$(echo "${share}" | sed 's@/@_@g')"		#挂载位置的根目录
			if [[ -z ${folder} ]] || [[ "/" = "${folder}" ]]; then	#挂载整个根目录
				link_path="${MPD_PATH}"
				rtn=$?
			else
				target_dir="${target_dir}${folder}"
				link_path="${link_dir}"
			fi
			echo -e "文件夹不存在，创建软链" >> "${SMB_USE_RECONNECT_lOG}"
			ln -snf "${target_dir}" "${link_path}" >> "${SMB_USE_RECONNECT_lOG}" 2>&1
			rtn=$?
			if [[ 0 -eq ${rtn} ]]; then
				echo -e "软链创建成功" >> "${SMB_USE_RECONNECT_lOG}"
				if [[ -d "${link_path}" ]]; then
					echo -e "文件夹存在" >> "${SMB_USE_RECONNECT_lOG}"
					echo "2"
					return 0
				else
					echo -e "文件夹不存在" >> "${SMB_USE_RECONNECT_lOG}"
					echo "202"
				fi
			else
				echo -e "软链创建失败" >> "${SMB_USE_RECONNECT_lOG}"
				echo "204"
			fi
		elif [[ "${mount_info}" =~ "${dir}.mount already exists." ]]; then
			echo "306"
		elif [[ "${mount_info}" =~ "Couldn't chdir to ${dir}: No such file or directory"$ ]]; then
			echo "307"
		else
			echo "300"		#挂载失败	
		fi
		echo -e "\t\t$(date +%s) \n${smb}挂载到${dir}失败：${mount_rtn}原因：\n${mount_info}" >> "${SMB_USE_RECONNECT_lOG}"
		return ${mount_rtn}
	fi
}


#文件夹设置使用成功后，如果有匹配就替换，没有就将信息插入存储文件的第一行。
function t_nas_insert(){
	echo -e "t_nas_insert : \n\t${1}\n\t${2}"
	if [[ -z "${1}" ]] || [[ -z "${2}" ]]; then
		return 1
	fi
	local all="${1}${2}"
	if [[ -e "${SMB_USED_RECORD}" ]]; then
		line=$(python "${PYTHON_GREP}" "${SMB_USED_RECORD}" "${1}")
		if [[ -n ${line} ]]; then		#有匹配就替换
			echo "替换第 ${line} 行"
			sed -i "${line}c ${all}" "${SMB_USED_RECORD}"
		else
			echo "追加内容"
			echo "${all}" >> "${SMB_USED_RECORD}"
		fi
	else
		parent_dir=$(dirname "${SMB_USED_RECORD}")
		if [[ ! -d "${parent_dir}" ]]; then
			echo "创建文件夹"
			mkdir -p "${parent_dir}"
		fi
		echo "创建记录文件"
		echo "${all}" > "${SMB_USED_RECORD}"
	fi
}

#删除记录表第一项匹配
function t_nas_delete(){
	echo "t_nas_delete : ${1}"
	if [[ -z "${1}" ]]; then
		return 1
	fi

	if [[ -e "${SMB_USED_RECORD}" ]]; then
		line=$(python "${PYTHON_GREP}" "${SMB_USED_RECORD}" "${1}")
		if [[ -n ${line} ]]; then		#有匹配就删除
			echo "删除第 ${line} 行"
			sed -i "${line}d" "${SMB_USED_RECORD}"
		fi
	fi
}

#状态修改
function t_nas_state_change(){
	echo -e "t_nas_state_change : \n\t${1}\n\t${2}"
	if [[ -z "${1}" ]] || [[ -z "${2}" ]]; then
		return 1
	fi
	line=$(python "${PYTHON_GREP}" "${SMB_USED_RECORD}" "${1}")
	if [[ -n ${line} ]]; then
		sed -i "${line}s/,\"state\":\".*\"}$/,\"state\":\"${2}\"}/" "${SMB_USED_RECORD}"		#修改指定行的状态
	fi
}

#开机时自动挂载samba设备
function t_smb_boot_run(){
	echo "start--开机挂载记录的samba设备--$(date +%s)"
	while (true); do
		sleep 1s
		ip=$(ifconfig eth0 | awk '{print $2}' | grep -E -o "([0-9]{1,3}[\.]){3}[0-9]{1,3}")
		if [[ -n ${ip} ]]; then

			if [[ ! -e "${SMB_lOG_DIR}" ]]; then
				mkdir -p "${SMB_lOG_DIR}"
			fi
			echo -e "开机挂载开始 $(date +%s)" > "${SMB_MOUNT_lOG}"

			if [[ ! -d "${MOUNT_PATH}" ]]; then
				mkdir -p "${MOUNT_PATH}" >> "${SMB_MOUNT_lOG}" 2>&1
			fi
			if [[ ! -d "${MOUNT_PATH}" ]]; then		#media/nas 文件夹创建失败
				echo "${MOUNT_PATH} 文件夹创建失败" >> "${SMB_MOUNT_lOG}"
				return 1
			fi

			#循环进行挂载
			IFS_old=$IFS
			IFS=$'\n'
			for line in $(cat "${SMB_MOUNT_RECORD}");do
				local query=$(echo "${line}" | grep -Po 'query[" :]+\K[^"]+')
				t_mount1 "${query}" >> "${SMB_MOUNT_lOG}" 2>&1
			done
			IFS=$IFS_old

			echo -e "开机挂载结束 $(date +%s)" >> "${SMB_MOUNT_lOG}"

			mpc update "nas"
			echo "${ip} 更新mpd的nas文件夹--$(date +%s)"
			return
		fi
	done
}

# 网络设置后重新挂载NAS
function t_smb_net_modify_run(){
	echo "网络已重启" > "${SMB_MOUNT_lOG}"
	mpc | grep "^\[playing" >> "${SMB_MOUNT_lOG}"
		status=$?
	 
	systemctl stop mpd.socket >> "${SMB_MOUNT_lOG}"
	systemctl stop mpd >> "${SMB_MOUNT_lOG}"
	systemctl stop upmpdcli >> "${SMB_MOUNT_lOG}"

	umount /media/nas/* >> "${SMB_MOUNT_lOG}"

	IFS_old=$IFS
	IFS=$'\n'
	for line in $(cat "${SMB_MOUNT_RECORD}");do
		local query=$(echo "${line}" | grep -Po 'query[" :]+\K[^"]+')
		t_mount1 "${query}" >> "${SMB_MOUNT_lOG}" 2>&1
	done
	IFS=$IFS_old

	systemctl start mpd.socket >> "${SMB_MOUNT_lOG}"
	systemctl start mpd >> "${SMB_MOUNT_lOG}"

	if [ $status -eq 0 ]; then
		mpc play >> "${SMB_MOUNT_lOG}"
	fi

	m1-dlna-renderer-init >> "${SMB_MOUNT_lOG}"
}

function t_mount1(){
	ip=$(echo "${1}" | grep -Po 'ip[=]+\K[^&]+' | urldecode | grep -E -o "([0-9]{1,3}[\.]){3}[0-9]{1,3}")
	if [[ -z "${ip}" ]]; then
		echo "没有IP"		#通过主机名获取ip地址失败
		return 1
	fi
	share=$(echo "${1}" | grep -Po 'share[=]+\K[^&]+' | urldecode)
	if [[ -z ${share} ]]; then
		echo "没有目录"		#没传入 文件夹名称
		return 1
	fi
	smb="//${ip}/${share}"		#samba服务器ip和要挂载的文件夹路径
	dir="${MOUNT_PATH}${ip}_$(echo "${share}" | sed 's@/@_@g')"		#挂载目录的文件夹完整路径
	echo -e "smb：${smb}\ndir：${dir}"
	if [[ ! -d "{dir}" ]]; then		#创建文件夹
		mkdir -p "${dir}"
	fi

	#获取密码并解密
	psd=""
	password=$(echo "${1}" | grep -Po 'password[=]+\K[^&]+' | urldecode)
	if [[ -n "${password}" ]]; then
		psd=$(thunder_aes_cbc128 "${password}")		#密码解析
		if [[ -z "${psd}" ]]; then
			echo -e "解密前密码：${password}"
			echo "密码解析失败"
			return 1
		fi
	fi
	#获取用户名并挂载
	user=$(echo "${1}" | grep -Po 'user[=]+\K[^&]+' | urldecode)
	if [[ -n "${user}" ]]; then
		echo -e "user${user}\npassword：${password}"
		mount -t cifs -v "${smb}" "${dir}" -o username="${user}",password="${psd}",iocharset=utf8 2>&1
		mount_rtn=$?
	else
		mount -t cifs -v "${smb}" "${dir}" -o password="${psd}",iocharset=utf8 2>&1
		mount_rtn=$?
	fi
	if [[ ${mount_rtn} -ne 0  ]]; then
		if [[ -n "${user}" ]]; then
			mount_info=$(mount -t cifs -v "${smb}" "${dir}" -o username="${user}",password="${psd}",iocharset=utf8,vers=2.0 2>&1)
			mount_rtn=$?
		else
			mount_info=$(mount -t cifs -v "${smb}" "${dir}" -o password="${psd}",iocharset=utf8,vers=2.0 2>&1)
			mount_rtn=$?
		fi
	fi
	if [[ ${mount_rtn} -ne 0  ]]; then
		if [[ -n "${user}" ]]; then
			mount_info=$(mount -t cifs -v "${smb}" "${dir}" -o username="${user}",password="${psd}",iocharset=utf8,vers=1.0 2>&1)
			mount_rtn=$?
		else
			mount_info=$(mount -t cifs -v "${smb}" "${dir}" -o password="${psd}",iocharset=utf8,vers=1.0 2>&1)
			mount_rtn=$?
		fi
	fi
	echo "挂载结果:${mount_rtn}"
}


case "${1}" in
	"boot_run" )		#开机运行
		t_smb_boot_run
		;;
	"net_modify_run" )		#网络修改后重启
		t_smb_net_modify_run
		;;
	"used_list" )		#已设置使用的nas
		t_used_list
		;;
	"used_list_light" )		#已设置使用的nas，不返回状态
		t_used_list_light
		;;
	"used_item_status" )		#使用的nas文件夹的状态
		t_used_item_status "${2}"
		;;
	"used_item_status_ignore_smbclient" )		#使用的nas文件夹的状态,忽略smbclient连线检查
		t_used_item_status_ignore_smbclient "${2}"
		;;
	"remove_nas" )		#删除软链停止使用文件夹
		t_remove_nas "${2}"
		;;
	"enable_nas" )		#启用已设置使用的nas文件夹
		t_enable_nas "${2}"
		;;
	"disable_nas" )		#禁用已设置使用的nas文件夹
		t_disable_nas "${2}"
		;;
	"reconnect_nas" )		#已断线的nas文件夹重连
		msg=$(t_reconnect_nas "${2}")
		rtn=$?
		echo -n "{\"status\":${rtn},\"message\":\"${msg}\"}"
		;;
	"samba_list" )		#局域网内samba列表
		t_samba_list
		;;
	"mount_nas" )		#挂载samba设备
		msg=$(t_mount_nas "${2}")
		rtn=$?
		if [[ 0 -eq ${rtn} ]]; then
			echo -n "${msg}"
		else	
			echo -n "{\"status\":${rtn},\"message\":\"${msg}\"}"
		fi
		;;
	"umount_nas" )		#卸载samba设备
		msg=$(t_umount_nas "${2}")
		rtn=$?
		echo -n "{\"status\":${rtn},\"message\":\"${msg}\"}"
		;;
	"show_dir" )		#显示目录里的文件夹列表
		t_show_dir_by_url "${2}"
		;;
	"use_nas" )		#创建软链使用文件夹
		t_use_nas "${2}"
		;;
	* )
		echo -n "{\"status\":98,\"message\":\"987\"}"		#指令错误
		exit 98
		;;
esac
exit $?
