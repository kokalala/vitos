#!/bin/sh

####################################################################
# Created by wannoo on 2019/07/23
# 读取日志文件相关
####################################################################

function json_result(){
	msg=$(${1})
	res=$?
	echo "\"status\":${res},\"message\":\"${msg}\","
}

function analysis(){
	alias urldecode='sed "s@+@ @g;s@%@\\\\x@g" | xargs -0 printf "%b"'
	local query=$(echo "${1}" | urldecode)
	for str in ${query//&/ }           #使用&进行分割
	do
		local key=$(echo ${str%%=*})
		local value=$(echo ${str##*=})
		case "${key}" in
			"samba_manage" )		#samba操作相关
				sh /srv/sh/app_smb.sh "${value}" "${1}"
				return
			;;
			"usb_manage" )		#usb操作相关
				sh /srv/sh/app_usb.sh "${value}" "${1}"
				return
			;;
			"device_manage" )		#设备信息或设置
				sh /srv/sh/app_device.sh "${value}" "${1}"
				return
			;;
			"dac_manage" )		#dac操作相关
				sh /srv/sh/app_dac.sh "${value}" "${1}"
				return
			;;
			"mpd_manage" )		#mpd操作相关
				sh /srv/sh/app_mpd.sh "${value}" "${1}"
				return
			;;
			"radio_manage" )		#广播操作相关
				sh /srv/sh/app_shoutcast.sh "${value}" "${1}"
				return
			;;
			"dlna_manage" )		#dlna操作相关
				sh /srv/sh/app_dlna.sh "${value}" "${1}"
				return
			;;
			"apps_manage" )		#应用操作相关
				sh /srv/sh/app_apps.sh "${value}" "${1}"
				return
			;;
			"shoutcast" )		#应用操作相关
				if [[ "info" = "${value}" ]]; then
					sh /srv/sh/app_shoutcast.sh "${value}" "json"
				else
					sh /srv/sh/app_shoutcast.sh "${value}" "${1}"
				fi
				return
			;;
			"hra_manage" )
				python "/srv/py/hra_streaming_api.py" "${value}" "${1}" 2>/dev/null
				return
			;;
			"hra_play" )
				python "/srv/py/hra_play.py" "${value}" "${1}" 2>/dev/null
				return
			;;
			"qobuz_manage" )
				python "/srv/py/qobuz/raw.py" "${value}" "${1}" 2>/dev/null
				return
			;;
			"qobuz_play" )
				python "/srv/py/qobuz/qobuz_play.py" "${value}" "${1}" 2>/dev/null
				return
			;;
			"tidal_manage" )
				python "/srv/py/tidal/airable_tidel.py" "${value}" "${1}" 2>/dev/null
				return 
			;;
			"amazon_manage" )
				python "/srv/py/amazon/airable_amazon.py" "${value}" "${1}" 2>/dev/null
				return 
			;;
			"tunein_manage" )
				python "/srv/py/tunein/tunein.py" "${value}" "${1}" 2>/dev/null
				return 
			;;
			"manage" )		#设备管理
				. "/srv/sh/app_manage.sh" > /dev/null
				case "${value}" in
					"reboot" )		#重启
						info="$(json_result saos_reboot)"
					;;
					"reboot1" )		#重启
						info="$(json_result saos_reboot1)"
					;;
				esac
				break;
			;;
			"roon_bridge_manage" )		#管理roon
				. "/srv/sh/app_roon_bridge.sh" > /dev/null
				case "${value}" in
					"install" )		#roon安装
						info="$(json_result roon_install_start)"
					;;
					"install_cancel" )		#取消roon下载
						info="$(json_result roon_install_cancel)"
					;;
					"restart" )		#roon重启
						info="$(json_result roon_restart)"
					;;
					"start" )		#roon开启
						info="$(json_result roon_start)"
					;;
					"stop" )		#roon停止
						info="$(json_result roon_stop)"
					;;
				esac
				break;
			;;
			"upgrade" )		#版本更新开始或取消下载
				case "${value}" in
					"start" )		#开始固件更新
						upgrade_msg=$(flock -n /tmp/vitos_lock_app_upgrade sh /srv/sh/app_versions_update_start.sh 2>&1)
						upgrade_rtn=$?
						if [[ 1 -eq ${upgrade_rtn} ]]; then
							info="\"status\":2,\"message\":\"202\","
						else
							info="\"status\":${upgrade_rtn},\"message\":\"${upgrade_msg}\","
						fi
					;;
					"cancel" )		#取消固件下载						
						if [[ -e "/tmp/vitos_lock_app_upgrade" ]]; then
							rm -f "/tmp/vitos_lock_app_upgrade"
						fi
						. "/srv/sh/app_versions.sh" > /dev/null
						info="$(json_result vitos_saos_upgrade_cancel)"
					;;
				esac
				break;
			;;
			"network_manage" )		#版本更新开始或取消下载
				. "/srv/sh/app_network.sh" > /dev/null
				case "${value}" in
					"set_dhcp" )		#设置为DHCP
						info="$(json_result network_set_dhcp)"
					;;
					"set_static" )		#设置为静态
						static_msg=$(network_set_static "${1}")
						local static_res=$?
						info="\"status\":${static_res},\"message\":\"${static_msg}\","
					;;
					"is_succeed" )		#判断新设置的网络是否能连接
						succeed_msg=$(network_set_succeed "${2}")
						local succeed_res=$?
						info="\"status\":${succeed_res},\"message\":\"${succeed_msg}\","
					;;
					"set_recover" )		#删除新设置的网络,只保留原来的
						faild_msg=$(network_set_faild "${2}")
						local faild_res=$?
						info="\"status\":${faild_res},\"message\":\"${faild_msg}\","
					;;
				esac
				break;
			;;
			"versions" )		#版本更新相关信息
				. "/srv/sh/app_versions.sh" > /dev/null
				if [[ "1" == "${value}" ]]; then
					. "/srv/sh/app_device.sh" > /dev/null
					info="$(get_version_local_info),$(get_device_name_info),$(vitos_saos_versions_info),"
				else
					info="$(vitos_saos_versions_info),"
				fi
				break;
			;;
			"device" )
				. "/srv/sh/app_device.sh" > /dev/null
				case "${value}" in
					"versions_local" )		#设备当前版本
						info="${info}$(get_version_local_info),"
					;;
					"device_name" )		#设备当前名称
						info="${info}$(get_device_name_info),"
					;;
					"run_time" )		#已开机运行的时间
						info="${info}$(get_running_time),"
					;;
					* )		#返回首页全部数据
						info="${info}$(get_device_all ${2}),"
					;;
				esac
			;;
			"network" )		#返回首页全部数据
				. "/srv/sh/app_network.sh" > /dev/null
				case "${value}" in
					"mac" )		#设备网络信息-mac
						. "/srv/sh/app_device.sh" > /dev/null
						info="${info}\"model\":\"m1\",$(get_device_name_info),$(get_network_info_mac),"
					;;
					* )		#设备网络信息-所有
						info="${info}$(get_network_info),"
					;;
				esac
			;;
			"sata" )		#硬盘信息
				. "/srv/sh/app_storage.sh" > /dev/null
				info="${info}$(get_sata_info),"
			;;
			"storage" )		#硬盘信息和USB信息
				. "/srv/sh/app_storage.sh" > /dev/null
				info="${info}$(get_sata_info),"
			;;
			"roon_bridge" )		#获取roon相关信息
				. "/srv/sh/app_roon_bridge.sh" > /dev/null
				info="${info}$(get_roon_info),"
			;;
			"time_manage" )  #时间管理
			    . "/srv/sh/app_time.sh" > /dev/null 2>&1
			    case "${value}" in
			         "get_status" )  #获取当前状态
			             info="$(vitos_time_status),"
			             ;;
			         "get_zone_list" )  #获取时区列表
			             info="$(vitos_time_get_zone_list),"
			             ;;
			         "set_zone" )  #设置时区
			             info="$(vitos_time_set_zone "${query}"),"
			             ;;
			         "set_date" )  #设置日期 yyyy-MM-dd
			             info="$(vitos_time_set_date "${query}"),"
			             ;;
			         "set_time" )  #设置时间 hh:mm:ss
			             info="$(vitos_time_set_time "${query}"),"
			             ;;
			         "set_auto" )  #设置自动
			             info="$(vitos_time_set_auto "${query}"),"
			             ;;
			         "set_manual" )  #设置手动
			             info="$(vitos_time_set_manual),"
			             ;;
			         "set_auto_update" )  #自动更新
			             info="$(vitos_time_set_auto_update "${query}"),"
						;;  
				esac
				break;
		     ;;
		esac
	done
	if [[ -z "${info}" ]]; then		#get参数没有正常解析出来
		echo "{\"code\":5,\"parameters\":\"${query}\"}"
		return 5
	fi
	echo -n "{"
	echo -n "${info}"
	echo -n "\"code\":0"
	echo "}"
}

function analysis_post(){
	if [[ "${1}" =~ ^samba_manage=[u]?mount_nas\&|\&samba_manage=[u]?mount_nas\&|\&samba_manage=[u]?mount_nas$ ]]; then
		local command=$(echo "${1}" | grep -Po '^samba_manage[=]+\K[^&]+|\&samba_manage[=]+\K[^&]+')
		. "/srv/sh/app_smb.sh" > /dev/null 2>&1
		msg=$(${command} "${1}")
		local res=$?
		echo "\"status\":${res},\"message\":\"${msg}\","
	else
		analysis "${1}" "${2}"
	fi
}

#第1个参数 get参数键值对
#第2个参数 当前请求的IP
#第3个参数 不为空为post请求
if [[ -n "${3}" ]]; then
	analysis_post "${1}" "${2}"
else
	analysis "${1}" "${2}"
fi