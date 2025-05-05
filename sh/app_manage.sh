#!/bin/sh

####################################################################
# Created by wannoo on 2019/07/24
# app管理设备
####################################################################

#重启
function saos_reboot(){
	. /srv/sh/app_versions.sh
	msg=$(vitos_saos_versions_log)
	if [[ $? -eq 3 ]]; then			#更新中不允许重启
		echo "300"		#Updating firmware, DO NOT reboot
		return 3
	fi
	
	#停止广播，防止等待重启时，设备被找到
	systemctl stop bcast_server > /dev/null 2>&1

	#停止mpd全部服务，否则重启时间太长
	systemctl stop upmpdcli > /dev/null 2>&1 && systemctl stop mpd.socket > /dev/null 2>&1 && systemctl stop mpd > /dev/null 2>&1

	# systemctl reboot -f
	# 为了在关机时显示logo，去掉-f，2019-11-29
	# 不需要接屏幕显示logo，加上-f，2021-03-29
	# 測試重複重啟. reboot 加上 -f 會有問題，去掉-f，2021-04-13
	systemctl reboot
	return $?
}

# #重启
# function saos_reboot1(){
# 	tasks="bcast_server lighttpd upmpdcli mpd.socket mpd dhcpcd"
# 	for task in ${tasks}; do
# 		msg=$(ps -aux | grep -E " ${task}" | grep -v "grep" | awk '{print $2}')
# 		for pid in ${msg}; do
# 			kill -9 "${pid}" > /dev/null 2>&1
# 			# echo "${pid}"
# 		done
# 	done
# 	systemctl reboot -f
# 	return $?
# }
# #重启
# function t_reboot(){
# 	tasks="bcast_server lighttpd upmpdcli mpd.socket mpd dhcpcd"
# 	for task in ${tasks}; do
# 		# echo "${task}"
# 		echo "$(ps -aux | grep -E "${task}" | grep -v "grep")"
# 		# msg=$(ps -aux | grep -E " ${task}" | grep -v "grep" | awk '{print $2}')
# 		# msg=$(ps -aux | grep -E "${task}" | grep -v "grep")
# 		# for pid in ${msg}; do
# 		# 	# kill -9 "${pid}" > /dev/null 2>&1
# 		# 	echo "${msg}"
# 		# done
# 	done
# }


# case "${1}" in
# 	"reboot" )		#机器重启
# 		t_reboot
# 		;;
# 	* )
# 		echo -n "{\"status\":98,\"message\":\"987\"}"		#指令错误
# 		exit 98
# 		;;
# esac
# exit $?
