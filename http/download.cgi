#!/bin/sh

####################################################################
# Created by wannoo on 2019/05/30
# 传递文件给web
####################################################################

function t_get_path(){
	if [[ -z "${1}" ]]; then
		echo "101"
		return 1
	fi
	if [[ "${1}" =~ ^"log_mpd" ]]; then		#VitOS_Player_Log_年月日_時分秒.zip
		time="${1:8}"
		if [[ -z "${time}" ]]; then
			log_tmp_path="/tmp/VitOS_Player_Log.zip"
		else
			log_tmp_path="/tmp/VitOS_Player_Log_${time}.zip"
		fi
		log_dir="/mnt/mpd/log"
		msg=$(zip -r -j "${log_tmp_path}" "${log_dir}" 2>&1)   #将RoonServer/Logs所有文件打包成 zip文件
		rtn=$?
		if [[ 0 -eq ${rtn} ]]; then
			echo "${log_tmp_path}"
			return 0
		else
			# echo "${msg}" | sed -n '1p' 
			echo "20${rtn}"
			return ${rtn}
		fi
	fi
	echo "109"
	return 1
}

#根据不同指令找到需要下载的文件下载地址，执行下载任务
function t_download(){
	msg=$(t_get_path "${1}")
	rtn=$?
	if [[ 0 -eq ${rtn} ]]; then
		echo -e "Content-Disposition:attachment;filename=$(basename ${msg})"
		echo -e "Content-Length:$(ls -l ${msg} | awk '{print $5}')"
		echo -e "Content-type:application/octet-stream\n"
		cat "${msg}"		#传输文件流
	else
		echo -e "Content-type: text/plain;charset=utf-8\n"
		echo -n "{\"status\":${rtn},\"message\":\"${msg}\"}"
	fi
}

alias urldecode='sed "s@+@ @g;s@%@\\\\x@g" | xargs -0 printf "%b"'	
t_download "$(echo $QUERY_STRING | urldecode)"



# msg="The file is not allowed to download"
# alias urldecode='sed "s@+@ @g;s@%@\\\\x@g" | xargs -0 printf "%b"'
# for str in ${1//&/ }; do
# 	case "$(echo ${str%%=*})" in
# 		"log_mpd" )
# 			time=$(echo ${str##*=} | urldecode)
# 			if [[ -z "${time}" ]]; then
# 				echo "102"
# 				return 1
# 			fi
# 			echo "${time}"
# 		;;
# 	esac
# done
