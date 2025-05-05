#!/bin/sh

####################################################################
# Created by wannoo on 2019/11/08
# roon_bridge安装
####################################################################

echo "2 json"
json=$(curl -s http://silentangel.audio/files/saos/roon_bridge.json 2>&1)
if [[ "$json" =~ "thunder_roon_link" ]]
then		#如果不存在thunder_version标签就默认为异常
	echo "2 url"
	url=$(echo "${json}" | grep -Po 'thunder_roon_link[" :]+\K[^"]+')
	md5=$(echo "${json}" | grep -Po 'md5[" :]+\K[^"]+')
	if [[ -z "${url}" ]] || [[ -z "${md5}" ]] ; then
		echo "0 url"
		return 2
	fi
	log="/tmp/vitos_roon_install/roon_install.log"
	kill_down="/srv/sh/roon_install_kill.sh"
	sh "/srv/sh/saos_app_install.sh" -u $url -i $md5 -l $log -k $kill_down
	exit $?
else
	echo "0 json"
	exit 1
fi