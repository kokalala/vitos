#!/bin/sh

####################################################################
# Created by wannoo on 2019/07/23
# 版本信息相关
####################################################################

vitos_update_log="/tmp/vitos_log_firmware_update.log"		#更新时的日志
vitos_update_sh_log="/tmp/vitos_log_firmware_update_sh.log"		#更新时更新脚本的日志
vitos_update_versions_new="/tmp/vitos_update_new_firmware_versions"		#另一个分区已安装好的最新版本号
vitos_update_versions_backups="/tmp/vitos_update_versions_backups"		#更新前将版本信息备份下来
vitos_update_kill_download="/tmp/vitos_update_kill_download.sh"		#更新时的日志

#获取当前设备版本
#版本文件存储在 /sbin/thunder_version 文件里
#示例返回: SAOS-1.0.0-20190412154131
function vitos_saos_versions_local(){
	local version=$(thunder_version 2>/dev/null)
	if [[ -z ${version} ]]; then
		echo "M1-0.0.0-0"
		return 1
	fi
	echo "${version}"
	return 0
}

#向服务器请求json数据  192.168.8.31 silentangel.audio
#示例返回:{"thunder_version": "thunder_v2.0_20190328","link": "https://www.baidu.com/","message": "这个版本修改了很重要的东西，建议更新。"}
function vitos_saos_versions_json(){
	if [[ -e "/mnt/settings/device_mode" ]]; then
		device_mode=$(cat "/mnt/settings/device_mode")
	fi
	if [[ -z ${device_mode} ]]; then
		saos="saos"
	else
		saos="saos.${device_mode}"
	fi
	local json=$(curl -s -m 50 http://silentangel.audio/files/${saos}/m1_versions.json 2>&1)
	if [[ "${json}" =~ "thunder_version" ]]
	then		#如果不存在thunder_version标签就默认为异常
		echo "${json}"
		return 0
	else
		echo "601"
		return 6
	fi
}

#传入服务器上得到的json信息,提取 最新版本号
#传入参数: 从服务器获取到的json信息
#示例返回: SAOS-1.0.0-20190412154131
function vitos_saos_versions_server(){
	if [[ -z ${1} ]]; then
		json=$(vitos_saos_versions_json)
	else
		json="${1}"
	fi
	local version=$(echo ${json} | grep -Po 'thunder_version[" :]+\K[^"]+')		#新的版本号
	if [ -z ${version} ] || [[ ${#version} -le 6 ]]; then		#判断获取到的返回值是否为空; 测试时遇到传入的参数出错时,获取到的返回值为":"
		echo "602"
		return 6
	fi
	echo "${version}"
	return 0
}

#传入服务器上得到的json信息,提取 下载链接
#传入参数: 从服务器获取到的json信息
#示例返回: http://silentangel.audio/files/saos/SAOS-1.0.286-20190422211314.tar.bz2
function vitos_saos_versions_link(){
	if [[ -z ${1} ]]; then
		json=$(vitos_saos_versions_json)
	else
		json="${1}"
	fi
	local file_link=$(echo ${json} | grep -Po 'link[" :]+\K[^"]+')		#更新文件链接
	if [ -z ${file_link} ] || [[ ${#file_link} -le 6 ]]; then		#判断获取到的返回值是否为空; 测试时遇到传入的参数出错时,获取到的返回值为":"
		echo "603"
		return 6
	fi
	echo "${file_link}"
	return 0
}

# 版本号比较
# 6：参数异常
# 3：版本一致
# 1：需要更新
# 2：无需更新
function vitos_saos_versions_compare(){
	if [[ -z ${1} ]] || [[ -z ${2} ]];then		#有一个为空直接返回
		return 6
	fi
	if [[ ${1} == ${2} ]];then		#如果版本号一样就直接返回
		return 3
	fi
	local info1=$(echo "${1}" | awk -v FS="-" '{print $2}' | grep -E -o "([0-9]*[\.])*[0-9]*")		#获取中间的数据:1.0.0
	local info2=$(echo "${2}" | awk -v FS="-" '{print $2}' | grep -E -o "([0-9]*[\.])*[0-9]*")
	array1=(${info1//./ })	#将服务器上的版本分解成数组
	array2=(${info2//./ })	#将服务器上的版本分解成数组
	for (( i = 0; i < 3; i++ )); do
		if [[ ${array1[i]} -gt ${array2[i]} ]]; then		#大于
			return 1
		elif [[ ${array1[i]} -lt ${array2[i]} ]]; then		#小于
			return 2
		fi
	done
	return 3 #三个数字都一样,或者异常情况,不需要更新
}

# 分析固件更新的日志
# 0：没有日志信息
# 2：下载中，输出下载进度
# 3：固件更新中，输出步骤编号
# 4：固件更新已完成，输出安装好的版本号
# 5：更新存在错误，返回错误码
function vitos_saos_versions_log(){
	[[ -z ${1} ]] && log_file=${vitos_update_log} || log_file=${vitos_update_sh_log}
	if [[ ! -e ${log_file} ]]; then
		echo "004"		#Log file does not exist
		return 0
	fi
	log=$(tail -n 1 ${log_file} 2> /dev/null)
	if [[ -z ${log} ]]; then
		echo "002"		#The log information is empty
		return 0
	fi
	if [[ -z ${1} ]] && [[ ${log} = "2 utar finish" ]]; then
		msg=$(vitos_saos_versions_log "sh_log" )
		if [[ $? -eq 3 ]]; then
			echo ${msg}
			return 3
		fi
	fi
	if [[ ${log} =~ ^"2 download " ]];then		#往外传递下载进度
		if [[ "progress" == $(echo ${log} | awk -n '{ print $3}') ]]; then		#更新文件下载中,示例:2 download progress 20.0;实际下载进度
			echo ${log} | awk -n '{ print $NF}'
		else		#下载开始前会写日志: 2 download 和 2 download url $url;下载进度0
			echo "0"
		fi
		return 2	
	fi
	if [[ ${log} =~ ^"1 end " ]]; then
		echo "${log}" | awk -F " " '{for (i=3;i<=NF;i++)printf("%s ", $i);print ""}'
		return 4
	fi
	local type=$(echo ${log} | awk '{ print $2}')		#比对第二个单词
	if [[ ${log} =~ ^"0 " ]]; then
		case "${type}" in
			"info")		#获取版本信息失败
				echo "${log}" | awk '{ print $3}'
			;;
			"download")		#0 download
				if [[ ${log} == "0 download kill" ]]; then		#0 download kill为用户主动取消
					echo "501"
				else
					echo "502"
				fi
			;;
			"utar")		#0 utar
				echo "503"
			;;
			"check")
				local subtype=$(echo ${log} | awk '{ print $3}')		#比对第三个单词
				[[ "img" == "${subtype}" ]] && echo "504" || echo "505"		#0 check img md5 或 0 check dd md5
			;;
			*)		#0 update grub config或者其他情况
				echo "506"
			;;
		esac
		return 5
	fi
	case "${type}" in
		"utar")		#2 utar  ;1 utar
			echo "301"
		;;
		"check")
			local subtype=`echo ${log} | awk '{ print $3}'`		#比对第三个单词
			[[ "img" == "${subtype}" ]] && echo "302" || echo "303"		#2 check img md5  ;1 check img md5 或 2 check dd md5  ;1 check dd md5
		;;
		"dd")		#2 dd img  ;1 dd img
			echo "304"
		;;
		"update")		#2 update grub config ;1 update grub config 或者 2 update firmware ;1 update firmware 
			echo "305"
		;;
		*)		#其他状况
			echo "306"
		;;
	esac
	return 3
}

# 获取版本更新状态和信息
# 0：无需更新
# 1：有最新的版本
# 2：下载中
# 3：更新中
# 4：已更新待重启
# 6：信息获取失败
# ${1}:不为空,只返回版本号、状态
function vitos_saos_versions_info(){
	msg=$(vitos_saos_versions_log)		#日志输出的信息
	rtn=$?		#日志获取状态码
	if [[ 2 -eq ${rtn} ]] || [[ 3 -eq ${rtn} ]]; then
		[[ -e ${vitos_update_versions_backups} ]] && server_message=$(cat ${vitos_update_versions_backups}) || server_message=$(vitos_saos_versions_json)
		message="${msg}"
		status=${rtn}
	else
		server_message=$(vitos_saos_versions_json)
		if [[ $? -eq 6 ]]; then
			message="${server_message}"
			status=6
		else
			server_version=$(vitos_saos_versions_server "${server_message}")
			compare=$(vitos_saos_versions_compare ${server_version} $(vitos_saos_versions_local))		#不是6或者1，就返回0，无需更新
			status=$?
			if [[ -n $(ps -aux | grep "sh /srv/sh/app_versions_update.sh" | grep -v " grep ") ]]; then
				message="307"
				status=3
			else
				message="${server_version}"
				if [[ 1 -eq ${status} ]]; then		#返回状态1，代表有新版本可更新
					if [[ 4 -eq ${rtn} ]] ;then		#更新日志上状态为:上次已更新未重启状态,再去和服务器上版本号比对一下
						vitos_saos_versions_compare "${server_version}" "${msg}"
						if [[ $? -ne 1 ]] && [[ -e ${vitos_update_versions_new} ]];then		#不需要更新,提示用户重启
							message="${msg}"
							status=${rtn}
						fi
					elif [[ 5 -eq ${rtn} ]]; then		#展示上次操作的错误信息,日志状态为5才有
						anomaly_info="${msg}"		#将日志文件读取到的错误信息以其他字段展出
					fi
				else
					status=0
				fi
			fi
		fi
	fi
	if [[ -n ${1} ]]; then		#只是获取更新状态
		echo "${message}"
		return ${status}
	fi
	#返回信息给app
	echo -n "\"status\":${status}"
	echo -n ",\"message\":\"${message}\""
	if [[ -n ${anomaly_info} ]];then		#展示上次操作的错误信息,状态为5才有
		echo -n ",\"anomaly_info\":\"${anomaly_info}\""
	fi
	if [[ 6 -ne ${status} ]] && [[ -n ${server_message} ]];then		#升级信息对话框要展示的信息,为jsonObject格式
		echo -n ",\"version_info\":{\"thunder_version${server_message#*thunder_version}"
	fi
	return ${status}
}

#开始固件更新
function vitos_saos_upgrade(){
	ps_upgrade=$(ps -aux | grep "sh /srv/sh/app_versions_update.sh" | grep -v " grep ")
	msg=$(vitos_saos_versions_info only_status)
	rtn=$?
	if [[ 2 -eq ${rtn} ]] || [[ 3 -eq ${rtn} ]]; then
		if [[ -z ${ps_upgrade} ]]; then
			echo "0 end" >> ${vitos_update_log} 
			msg=$(vitos_saos_versions_info only_status)
			rtn=$?
		fi
	fi
	if [[ 4 -eq ${rtn} ]]; then
		echo "400"
		return 4
	elif [[ 3 -eq ${rtn} ]]; then
		echo "${msg}"
		return 3
	elif [[ 2 -eq ${rtn} ]]; then
		echo "200"		#Update file download...
		return 2
	elif [[ 0 -eq ${rtn} ]]; then
		echo "100"		#Update file download...
		return 1
	fi
	if [[ -n ${ps_upgrade} ]]; then
		echo "201"
	  	return 2
	fi
	nohup sh /srv/sh/app_versions_update.sh > ${vitos_update_log} 2>/tmp/vitos_log_firmware_update_failed.log &
	echo "000"		#开始更新了 The update program is starting
	rm -f "/tmp/vitos_lock_app_upgrade"
	return 0
}

#取消固件更新的下载操作
function vitos_saos_upgrade_cancel(){
	if [[ -e ${vitos_update_kill_download} ]]; then
		msg=$(sh ${vitos_update_kill_download} 2>&1)
		local rtn=$?
		if [[ 0 -ne ${rtn} ]]; then
			echo -n ${msg}
		fi
		rm -f ${vitos_update_kill_download}
		return ${rtn}
	fi
	ps_upgrade=$(ps -aux | grep "sh /srv/sh/app_versions_update.sh" | grep -v " grep ")
	if [[ -z ${ps_upgrade} ]] && [[ -e ${vitos_update_log} ]]; then
		if [[ "$(tail -n 1 ${vitos_update_log})" =~ ^"2 " ]] ; then
			echo "0 download kill" >> ${vitos_update_log}
			return 0
		fi
	fi
	return 1
}
