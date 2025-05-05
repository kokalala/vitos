#!/bin/sh

####################################################################
# Created by wannoo on 2019/04/19
# applications应用信息相关,目前只有 Roon Server
#Status:Running Restarting… Stopped Starting…
#Button:Restart Start Stop
####################################################################

ROON="roonbridge"

#以json格式返回Roon Server版本信息,运行状态
function get_roon_info(){
	echo -n "\"roon\":{"
	get_roon_status
	local roon_status=$?
	if [[ 0 -eq ${roon_status} ]]; then		#roon运行中
		echo -n "\"status\":0,\"message\":\"$(get_roon_version)\""
	else
		install_log=$(analysis_roon_install_log)
		local install_log_result=$?
		if [[ 4 -eq ${roon_status} ]]; then		#没有安装
			if [[ 0 -eq ${install_log_result} ]]; then		#没有安装错误且不是下载或安装中
				echo  -n "\"status\":4,\"message\":\"\""
			else
				echo -n "\"status\":${install_log_result},\"message\":\"${install_log}\""
			fi
		else		#已安装，未运行。判断是否刚安装完成。
			if [[ 0 -eq ${install_log_result} ]]; then
				echo -n "\"status\":1,\"message\":\"$(get_roon_version)\""				#roon未运行
			else
				if [[ -e "/tmp/vitos_roon_install/roon_install_start.log" ]]; then
					local time0=$(stat "/tmp/vitos_roon_install/roon_install_start.log" | grep "Modify:" | sed 's/Modify: //g')
					local time1=$(date -d "${time0}" +%s)  
					if [[ $(($(date +%s) - ${time1})) -gt 5 ]]; then
						rm -rf "/tmp/vitos_roon_install/roon_install.log"
						rm -rf "/tmp/vitos_roon_install/roon_install_start.log"
						echo -n "\"status\":1,\"message\":\"$(get_roon_version)\""				#roon未运行
					else
						echo  -n "\"status\":3,\"message\":\"306\""
					fi
				fi
			fi
		fi
	fi
	echo -n "}"
}

#获取RoonServer版本信息
function get_roon_version(){
	local roon_version_path="/opt/RoonBridge/Bridge/VERSION"	#RoonServer版本信息存储位置
	if [ ! -e ${roon_version_path} ]		#没有安装RoonServer
	then
		echo "Roon Server is not installed"
		return 1
	fi
	echo $(sed -n 2p ${roon_version_path}) 	#读取版本文件第二行,示例返回:1.6 (build 401) stable
}

#获取Roon Server运行状态
#返回 4:没有安装  0:正常运行  3或者其他按没有运行处理
function get_roon_status(){
	roon_status=$(systemctl status $ROON 2> /dev/null) 	#获取RoonServer运行状态
	return $?	#直接把systemctl状态返回
}

#启动roonserver
function roon_start(){
	systemctl start $ROON 2> /dev/null
	return $?	
}

#关闭roonserver
function roon_stop(){
	systemctl stop $ROON 2> /dev/null
	return $?	
}

#重启roonserver
function roon_restart(){
	systemctl restart $ROON 2> /dev/null
	return $?	
}

#roon安装动作开始
function roon_install_start(){
	install_log=$(analysis_roon_install_log)
	local install_log_result=$?
	if [[ 2 -eq ${install_log_result} ]]; then		#下载中
		echo "200"
		return 2
	elif [[ 3 -eq ${install_log_result} ]]; then		#安装中
		echo "300"
		return 3
	fi
	if [[ ! -d "/tmp/vitos_roon_install/" ]]; then
		mkdir "/tmp/vitos_roon_install/"
	fi
	rm -rf "/tmp/vitos_roon_install/roon_install.log"
	echo "2 json" > "/tmp/vitos_roon_install/roon_install_start.log"
	nohup sh "/srv/sh/roon_install.sh" >> "/tmp/vitos_roon_install/roon_install_start.log" 2>&1 &
	if [[ $? -ne 0 ]]; then
		echo "100"
		return 1
	fi
	echo "000"
	return 0
}

#roon安装动作开始
function roon_install_cancel(){
	roon_install_kill=$(sh "/srv/sh/roon_install_kill.sh" 2> /dev/null)
	return $?
}

#解析roon安装日志
# 0失败 1成功 2进行中
# 2 json	从网络获取json数据
# 2 url	解析json获取下载地址
# 2 download	下载
# 2 check md5	校验
# 2 utar	解压
# 2 install	安装
# 1 install 安装成功
# return的参数说明：
# 0：没有在安装中；2：下载中；3：安装中；1：安装成功；5：出现出错
function analysis_roon_install_log(){
	if [[ -e "/tmp/vitos_roon_install/roon_install.log" ]];then
		local log=$(tail -n 1 "/tmp/vitos_roon_install/roon_install.log")
	elif [[ -e "/tmp/vitos_roon_install/roon_install_start.log" ]]; then
		local log=$(tail -n 1 "/tmp/vitos_roon_install/roon_install_start.log")
	else
		echo "0"		#没有日志
		return 0
	fi
	if [[ "${log}" == "1 install" ]]; then
		echo "300"		#安装成功		-Installed
		return 1
	elif [[ ${log} =~ ^0.* ]];then
		local type=`echo "${log}" | awk '{ print $2}'`		#比对第二个单词
		case "${type}" in
			"json")		#0 json		-Failed to retrieve package information
				echo "501"
			;;
			"url")		#0 url		-Failed to retrieve package download URL
				echo "502"
			;;
			"download")		#0 download		
				if [[ ${log} == "0 download kill" ]]; then		#0 download kill为用户主动取消		-Cancelled by user.
					echo "503"
				else
					echo "504"		#-Failed to download package
				fi
			;;
			"check")		#0 check md5		-Failed to check data integrity
				echo "505"
			;;
			"utar")		#0 utar		-Failed to uncompress package
				echo "506"
			;;
			*)		#0 install或者其他情况		-Failed to install package
				echo "507"
			;;
		esac
		return 5
	elif [[ "${log}" =~ ^"2 download" ]]; then		#往外传递下载进度
		if [[ "progress" == $(echo "${log}" | awk -n '{ print $3}') ]]; then		#更新文件下载中,示例:2 download progress 20.0;实际下载进度
			echo $(echo "${log}" | awk -n '{ print $NF}')
		else		#下载开始前会写日志: 2 download 和 2 download url $url;下载进度0
			echo "0"
		fi
		return 2	
	else
		local type=`echo "${log}" | awk '{ print $2}'`		#比对第二个单词
		case "${type}" in
			"json")		#2 json;1 json		-Retrieving package information
				echo "301"
			;;
			"url")		#2 url;1 url		-Retrieving package information
				echo "302"
			;;
			"download")		#1 download		-Downloading
				echo "303"
			;;
			"check")		#2 check md5;1 check md5		-Checking data integrity
				echo "304"
			;;
			"utar")		#2 utar;1 utar		-Uncompressing
				echo "305"
			;;
			*)		#2 install;1install或者其他情况		-Installing
				echo "306"
			;;
		esac
		return 3
	fi
	echo "0"
	return 0
}
