#!/bin/sh

##################################################
### tidal
### Created by wannoo on 2021/07/06
### last modified 2021/07/06
##################################################


alias urldecode='sed "s@+@ @g;s@%@\\\\x@g" | xargs -0 printf "%b"'

# 首页信息
function t_home_info(){
	echo -n "{\"status\":0,\"message\":\"0\""
	album=$(t_album_info id=1)
	echo -n ",\"albums\":[${album},${album},${album},${album},${album},${album}]"
	playlist=$(t_playlist_info id=1)
	echo -n ",\"playlists\":[${playlist},${playlist},${playlist}]"
	track=$(t_track_info id=1)
	echo -n ",\"tracks\":[${track},${track},${track},${track},${track},${track},${track},${track},${track},${track},${track},${track},${track},${track},${track},${track},${track},${track},${track},${track}]"
	echo "}"
}

# 专辑信息
function t_album_info(){
	id=$(echo "${1}" | grep -Po 'id[=]+\K[^&]+' | urldecode)
	if [[ -z "${id}" ]]; then
		echo -n "101"
		return 1
	fi

	info=$(cat /mnt/tidal_album.json 2>/dev/null | jq ".data.album" 2>/dev/null)
	if [[ -z "${info}" ]]; then
		echo -n "201"
		return 2
	fi


	echo ${info} | jq -c '. | {id ,title ,releaseDate ,artists ,type ,image}' | sed 's/}$//'
	echo ",\"tracks\":"
	echo ${info} | jq -c '[.tracks[] | {id ,title ,duration ,artists ,image ,albumID ,albumTitle}]'
	echo "}"
}

# 播放列表
function t_playlist_info(){
	id=$(echo "${1}" | grep -Po 'id[=]+\K[^&]+' | urldecode)
	if [[ -z "${id}" ]]; then
		echo -n "101"
		return 1
	fi

	info=$(cat /mnt/tidal_playlist.json 2>/dev/null | jq ".data.playlist" 2>/dev/null)
	if [[ -z "${info}" ]]; then
		echo -n "201"
		return 2
	fi

	echo ${info} | jq -c '. | {creator ,description ,uuid ,title ,type ,image}' | sed 's/}$//'
	echo ",\"tracks\":"
	echo ${info} | jq -c '[.tracks[] | {id ,title ,duration ,artists ,image ,albumID ,albumTitle}]'
	echo "}"
}

# 歌曲信息
function t_track_info(){
	id=$(echo "${1}" | grep -Po 'id[=]+\K[^&]+' | urldecode)
	if [[ -z "${id}" ]]; then
		echo -n "101"
		return 1
	fi

	info=$(cat /mnt/tidal_track.json 2>/dev/null | jq ".data.track" 2>/dev/null)
	if [[ -z "${info}" ]]; then
		echo -n "201"
		return 2
	fi

	echo ${info} | jq -c '. | {id ,title ,duration ,artists ,image ,albumID ,albumTitle}'
}

# 歌手信息
function t_artist_info(){
	id=$(echo "${1}" | grep -Po 'id[=]+\K[^&]+' | urldecode)
	if [[ -z "${id}" ]]; then
		echo -n "101"
		return 1
	fi

	info=$(cat /mnt/tidal_track.json 2>/dev/null | jq ".data.track" 2>/dev/null)
	if [[ -z "${info}" ]]; then
		echo -n "201"
		return 2
	fi

	echo ${info} | jq -c '. | {id ,title ,duration ,artists ,image ,albumID ,albumTitle}'
}



case "${1}" in
	"home" )		#首页
		t_home_info
		;;
	"album" )		#专辑信息
		msg=$(t_album_info ${2})
		rtn=$?
		if [[ 0 -eq ${rtn} ]]; then
			echo -n "{\"status\":0,\"message\":\"0\",\"album\":${msg}}"
		else
			echo -n "{\"status\":${rtn},\"message\":\"${msg}\"}"
		fi
		;;
	"playlist" )		#播放列表
		msg=$(t_playlist_info ${2})
		rtn=$?
		if [[ 0 -eq ${rtn} ]]; then
			echo -n "{\"status\":0,\"message\":\"0\",\"playlist\":${msg}}"
		else
			echo -n "{\"status\":${rtn},\"message\":\"${msg}\"}"
		fi
		;;	
	"track" )		#歌曲信息
		msg=$(t_track_info ${2})
		rtn=$?
		if [[ 0 -eq ${rtn} ]]; then
			echo -n "{\"status\":0,\"message\":\"0\",\"track\":${msg}}"
		else
			echo -n "{\"status\":${rtn},\"message\":\"${msg}\"}"
		fi
		;;
	"artist" )		#歌曲信息
		msg=$(t_track_info ${2})
		rtn=$?
		if [[ 0 -eq ${rtn} ]]; then
			echo -n "{\"status\":0,\"message\":\"0\",\"track\":${msg}}"
		else
			echo -n "{\"status\":${rtn},\"message\":\"${msg}\"}"
		fi
		;;
	* )
		echo -n "{\"status\":98,\"message\":\"987\"}"		#指令错误
		exit 98
		;;
esac
exit $?








# original=$(echo ${info} | jq .image.original)
# if [[ "null" = "${original}" ]]; then
# 	echo "1111"
# fi	
# large=$(echo ${info} | jq .image.large)
# if [[ "null" = "${large}" ]]; then
# 	echo "222"
# fi
# echo "3333"