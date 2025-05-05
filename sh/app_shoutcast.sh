#!/bin/sh

API_KEY="HLW5qCXJaD3ZhWMG"
alias urldecode='sed "s@+@ @g;s@%@\\\\x@g" | xargs -0 printf "%b"'

file_dir="/mnt/settings"
file_path="${file_dir}/vitos_radio_shoutcast.m3u"
info_path="${file_dir}/vitos_radio_shoutcast_info"


# 广播播放
# 一、不传入参数，直接播放之前存储的电台信息
# 二、传入参数base_m3u、radio_id、station_info

# 下载播放列表  
# http://yp.shoutcast.com<base>?id=[Station_id]
# 示例：curl -s -m 50 http://yp.shoutcast.com/sbin/tunein-station.m3u?id=99497996  -o tunein-station.m3u
# curl -s, --silent 不输出进度和错误信息 -m, --max-time <seconds> 最大请求时间
# 开始播放
# mpc clear
# mpc load /mnt/mpd/music/tunein-station.m3u
# mpc play
function t_shoutcast_play(){
	if [[ ! -d "${file_dir}" ]]; then
		mkdir -p "${file_dir}" >/dev/null 2>&1
	fi
	if [[ ! -d "${file_dir}" ]]; then
		echo "501"
		return 5
	fi
	base_m3u=$(echo "${1}" | grep -Po 'base_m3u[=]+\K[^&]+' | urldecode)
	radio_id=$(echo "${1}" | grep -Po 'radio_id[=]+\K[^&]+' | urldecode)
	play_app="/mnt/settings/radio-shoutcast-play"

	if [[ -z "${base_m3u}" ]] || [[ -z "${radio_id}" ]]; then
		if [[ -e "${file_path}" ]]; then
			head -1 "${info_path}" 2>/dev/null | sed 's|&|&amp;|g' | sed 's|<|\&lt;|g'
			touch ${play_app} >/dev/null 2>&1
			mpc clear >/dev/null 2>&1
			m1-hifi-play-app radio-shoutcast >/dev/null 2>&1
			mpc load "${file_path}" >/dev/null 2>&1 && mpc play >/dev/null 2>&1
			rtn=$?
			rm -rf ${play_app} >/dev/null 2>&1
			if [[ 0 -eq ${rtn} ]]; then		#播放成功
				return 0
			fi
		fi
	fi

	if [[ -z "${base_m3u}" ]]; then
		echo "102"
		return 1
	fi
	if [[ -z "${radio_id}" ]]; then
		echo "103"
		return 1
	fi


	curl -s -m 50 "http://yp.shoutcast.com${base_m3u}?id=${radio_id}" -o "${file_path}" >/dev/null 2>&1
	rtn=$?
	if [[ 0 -ne ${rtn} ]]; then
		echo "20${rtn}"		#下载失败
		return 2
	fi
	if [[ ! $(file ${file_path} 2>&1) =~ ^"${file_path}: M3U playlist" ]]; then
		echo "301"		#不是.m3u文件
		return 3
	fi

	station_info=$(echo "${1}" | grep -Po 'station_info[=]+\K[^&]+' | urldecode)
	if [[ -n "${station_info}" ]]; then
		echo "${station_info}" > "${info_path}"
		echo "${station_info}" | sed 's|&|&amp;|g' | sed 's|<|\&lt;|g'
	else
		> "${info_path}"
		echo "${radio_id}"
	fi

	touch ${play_app} >/dev/null 2>&1
	mpc clear >/dev/null 2>&1
	m1-hifi-play-app radio-shoutcast >/dev/null 2>&1
	mpc load "${file_path}" >/dev/null 2>&1 && mpc play >/dev/null 2>&1
	rtn=$?
	rm -rf ${play_app} >/dev/null 2>&1
	if [[ 0 -ne ${rtn} ]]; then
		echo "40${rtn}"		#播放失败
		return 4
	fi

	return 0
}

# 获取当前播放的电台的信息
function t_shoutcast_info(){
	if test -s "${info_path}"; then		#文件存在且不为空
		head -1 "${info_path}" 2>/dev/null | sed 's|&|&amp;|g' | sed 's|<|\&lt;|g'
		return 0
	fi
	echo "101"
	return 1
}

# 获取当前播放的电台的信息
function t_shoutcast_info_json(){
	if test -s "${info_path}"; then		#文件存在且不为空
		head -1 "${info_path}" 2>/dev/null | sed 's@\\@\\\\@g' | sed 's@\"@\\\"@g'
		return 0
	fi
	echo "101"
	return 1
}

case "${1}" in
	"top500" )		#前500列表	
		info=$(curl http://api.shoutcast.com/legacy/Top500?k=${API_KEY} 2>/dev/null)
		if [[ -n $(echo "${info}" | grep ^"<stationlist>") ]]; then
			echo -e "<response>\n<statusCode>200</statusCode>\n<statusText>Ok</statusText>\n<data>"
			echo "${info}"
			echo -e "</data>\n</response>"
		else
			echo "${info}"
		fi

		curl "http://api.shoutcast.com/legacy/Top500?k=${API_KEY}" 2>/dev/null

		# echo '<stationlist>'
		# echo '<tunein base="/sbin/tunein-station.pls" base-m3u="/sbin/tunein-station.m3u" base-xspf="/sbin/tunein-station.xspf"/>'
		# echo '<station name="ANTENNE BAYERN" mt="audio/mpeg" id="99497996" br="128" genre="Pop" ct="The Strumbellas - Spirits" lc="51446"/>'
		# echo '<station name="Dance Wave!" mt="audio/mpeg" id="1817772" br="128" genre="Electronic" ct="Francesco De Argentis - So Now" lc="21623"/>'
		# echo '<station name="COOLfahrenheit | Easy Listening" mt="audio/mpeg" id="1856883" br="256" genre="Easy Listening" ct="มาร์ค ธัชพล - ยังรอ..." lc="15705"/>'
		# echo '<station name="ROCK ANTENNE" mt="audio/mpeg" id="99498012" br="128" genre="Rock" ct="Spider Murphy Gang - Skandal im Sperrbezirk" lc="14254"/>'
		# echo '<station name="Dance Wave Retro!" mt="audio/mpeg" id="1631097" br="128" genre="Electronic" ct="Jimmy Sommerville - Comment Te Dire Adieu" lc="10718"/>'
		# echo '</stationlist>'
		;;
	"list" )		#根据ID查询广播列表
		genre_id=$(echo "${2}" | grep -Po 'genre_id[=]+\K[^&]+' | urldecode)
		if [[ -z "${genre_id}" ]]; then
			echo -e "<response>\n<statusCode>10087</statusCode>\n<statusText>Missing required parameter</statusText>\n<statusDetailText>genre_id is empty</statusDetailText>\n</response>"
			exit 2
		fi
		curl "http://api.shoutcast.com/station/advancedsearch?k=${API_KEY}&f=xml&genre_id=${genre_id}" 2>/dev/null
		;;
	"genre_primary" )		#主要分类
		curl "http://api.shoutcast.com/genre/primary?k=${API_KEY}&f=xml" 2>/dev/null
		;;
	"genre_secondary" )		#次级分类
		parentid=$(echo "${2}" | grep -Po 'parent_id[=]+\K[^&]+' | urldecode)
		if [[ -z "${parentid}" ]]; then
			echo -e "<response>\n<statusCode>10087</statusCode>\n<statusText>Missing required parameter</statusText>\n<statusDetailText>parentid is empty</statusDetailText>\n</response>"
			exit 2
		fi
		curl "http://api.shoutcast.com/genre/secondary?k=${API_KEY}&f=xml&parentid=${parentid}" 2>/dev/null
		;;
	"play" )		#配置表中的名称
		msg=$(t_shoutcast_play "${2}")
		rtn=$?
		echo -e "<response>\n<statusCode>200</statusCode>\n<statusText>${rtn}</statusText>\n<statusDetailText>${msg}</statusDetailText>\n</response>"
		;;
	"info" )		#获取当前播放的电台的信息
		if [[ "json" = "${2}" ]]; then
			msg=$(t_shoutcast_info_json)
			echo -n "{\"status\":$?,\"message\":\"${msg}\"}"
		else
			msg=$(t_shoutcast_info)
			echo -e "<response>\n<statusCode>200</statusCode>\n<statusText>$?</statusText>\n<statusDetailText>${msg}</statusDetailText>\n</response>"
		fi
		;;
	* )		#指令错误
		echo -e "<response>\n<statusCode>10086</statusCode>\n<statusText>Wrong interface</statusText>\n<statusDetailText>parameter:${1}</statusDetailText>\n</response>"
		exit 1
		;;
esac
exit $?