#!/bin/sh

##################################################
### mpd收藏列表
### Created by wannoo on 2020/1/7
##################################################

FAVORITE_URL="/data/vitos/playlists/thunder_system_favorite.m3u"
alias urldecode='sed "s@+@ @g;s@%@\\\\x@g" | xargs -0 printf "%b"'

function mpd_favorite_query(){
	if [[ -e "${FAVORITE_URL}" ]]; then
		cat "${FAVORITE_URL}"
	else		#文件不存在
		touch "${FAVORITE_URL}"
	fi
	echo "thunder_mpd_favorite_list"
}

function mpd_favorite_add(){
	if [[ -z "${1}" ]]; then
		echo "101"
		return 1
	fi
	local song=$(echo "${1}" | grep -Po 'song[=]+\K[^&]+' | urldecode)
	if [[ -z "${song}" ]]; then
		echo "102"
		return 2
	fi
	local is_add=$(grep -o -m 1 ^"${song}"$ "${FAVORITE_URL}" 2> /dev/null)
	if [[ -n "${is_add}" ]]; then
		echo "103"
		return 3
	fi
	echo "${song}" >> "${FAVORITE_URL}"

	local user=$(echo "${1}" | grep -Po 'user[=]+\K[^&]+' | urldecode)
	if [[ -z "${user}" ]]; then
		user="nobody"
	fi
	mpc sendmessage mpd_favorite "add ${user} ${song}" 2> /dev/null
	local res=$?
	echo ${res}
	return ${res}
}

function mpd_favorite_remove(){
	if [[ -z "${1}" ]]; then
		echo "101"
		return 1
	fi
	local song=$(echo "${1}" | grep -Po 'song[=]+\K[^&]+' | urldecode)
	if [[ -z "${song}" ]]; then
		echo "102"
		return 2
	fi
	local is_add=$(grep -o -m 1 ^"${song}"$ "${FAVORITE_URL}" 2> /dev/null)
	if [[ -z "${is_add}" ]]; then
		echo "103"
		return 3
	fi
	local song_sed=$(echo ${song} | sed 's:/:\\/:g')
	sed -i "/${song_sed}/d" "${FAVORITE_URL}" 2> /dev/null

	local user=$(echo "${1}" | grep -Po 'user[=]+\K[^&]+' | urldecode)
	if [[ -z "${user}" ]]; then
		user="nobody"
	fi
	mpc sendmessage mpd_favorite "remove ${user} ${song}" 2> /dev/null
	local res=$?
	echo ${res}
	return ${res}
}

# MPD重启
function t_restart_mpd(){
	systemctl stop mpd.socket
	systemctl stop mpd
	systemctl start mpd.socket
	systemctl start mpd
	m1-dlna-renderer-init
	return $?
}

# 清除数据库重新扫描音乐
function t_clear_database(){
	systemctl stop mpd.socket
	systemctl stop mpd
	rm "/mnt/mpd/mpd.db"
	systemctl start mpd.socket
	systemctl start mpd
	mpc rescan
	m1-dlna-renderer-init
	return $?
}

# 日志下载
function t_download_log(){
	mpd_log="/mnt/mpd/mpd.log"
	if [[ -e "${mpd_log}" ]]; then
		echo "${mpd_log}"
		return 0
	else
		echo "101"
		return 1
	fi
}
server1="mpd"
server2="mpd.socket"

# 以json格式返回版本信息,运行状态,应用名称
function t_mpd_info(){
	t_mpd_status ${server1}> /dev/null 2>&1
	echo "{\"mpd_status\":$?"
	t_mpd_status ${server2}> /dev/null 2>&1
	echo ",\"mpd_socket_status\":$?}"
}

# 获取运行状态：不输出信息，只返回代码 
# 返回 0:正常运行  3或者其他按没有运行处理	5:运行错误
function t_mpd_status(){
	systemctl status ${1} > /dev/null 2>&1 	#获取服务运行状态
	rtn=$?
	if [[ 3 -eq ${rtn} ]]; then
		if systemctl is-failed --quiet ${1} > /dev/null 2>&1; then
			return 5
		fi
	fi
	return $rtn	#直接把systemctl状态返回
}

# 将传进来的文件路径处理后返回
# samba需要通过记录表将ip和文件夹拆分
function t_file_details(){
	if [[ -z "${1}" ]]; then
		echo -n "{\"status\":1,\"message\":\"101\"}"
		return 1
	fi
	alias urldecode='sed "s@+@ @g;s@%@\\\\x@g" | xargs -0 printf "%b"'		#解码
	path=$(echo "${1}" | grep -Po 'path[=]+\K[^&]+' | urldecode)
	if [[ -z "${path}" ]]; then
		echo -n "{\"status\":1,\"message\":\"102\"}"
		return 1
	fi
	echo -n "{\"status\":0"
	message="other"
	if [[ "${path}" =~ ^"nas/" ]]; then
		smb="$(echo ${path:4})"
		smb="nas/$(echo ${smb%%/*})"
		echo -n ",\"path\":\"${smb}\""

		line=$(grep -E "\",\"path\":\"${smb}\",\"state\":\".+\"}"$ "/mnt/settings/vitos_smb_used_record" 2>/dev/null | sed -n '1p')
		if [[ -n ${line} ]]; then
			ip=$(echo "${line}" | grep -Po 'ip[" :]+\K[^"]+' | sed -n '1p')
			share=$(echo "${line}" | grep -Po 'share[" :]+\K[^"]+' | sed -n '1p')
			folder=""
			if [[ -z $(echo "${line}" | grep "\"folder\":\"\"") ]]; then
				folder=$(echo "${line}" | grep -Po 'folder[" :]+\K[^"]+' | sed -n '1p')
			fi
			details="$(echo ${path:${#smb}})"
			echo -n ",\"ip\":\"${ip}\",\"share\":\"${share}\",\"folder\":\"${folder}\""

			path="smb://${ip}/${share}${folder}${details}"
		fi
		message="nas"
	elif [[ "${path}" =~ ^"usb/" ]]; then
		usb="$(echo ${path:4})"
		usb="usb/$(echo ${usb%%/*})"
		echo -n ",\"path\":\"${usb}\""

		mountpoint=$(ls -l "/mnt/mpd/music/${usb}" 2> /dev/null | awk '{print $NF}')
		if [[ "${mountpoint}" =~ ^"/media/" ]]; then
			dev="/dev$(echo ${mountpoint:6})"
			label1=$(lsblk -no label -d ${dev} 2>/dev/null)
			label=$(python3 "/srv/py/app_str_decode.py" "${label1}" 2>/dev/null)
			echo -n ",\"mountpoint\":\"${mountpoint}\",\"label\":\"${label}\""
		fi

		path="USB://$(echo ${path:4})"
		message="usb"
	fi
	echo -n ",\"message\":\"${message}\""
	echo -n ",\"show_path\":\"$(echo "${path}" | sed 's@\\@\\\\@g' | sed 's@\"@\\\"@g')\""
	echo -n "}"
}

case "${1}" in
	"info" )		#开机运行
		t_mpd_info
		;;
	"restart" )		#MPD重启
		t_restart_mpd > "/tmp/vitos_log_mpd_restart.log"  2>&1
		rtn=$?
		echo -n "{\"status\":${rtn},\"message\":\"${rtn}\"}"
		;;	
	"clear_database" )		#清除数据库重新扫描音乐
		t_clear_database > "/tmp/vitos_log_mpd_clear_database.log" 2>&1
		rtn=$?
		echo -n "{\"status\":${rtn},\"message\":\"${rtn}\"}"
		;;	
	"download_log" )		#获取日志下载路径
		msg=$(t_download_log)
		rtn=$?
		echo -n "{\"status\":${rtn},\"message\":\"${msg}\"}"
		;;		
	"file_details" )		#将传进来的路径处理后返回
		t_file_details ${2}
		;;	
	* )
		echo -n "{\"status\":98,\"message\":\"987\"}"		#指令错误
		exit 98
		;;
esac
exit $?
