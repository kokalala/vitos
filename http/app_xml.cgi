#!/bin/sh

####################################################################
# Created by wannoo on 2020/12/11
# app和服务器交互
####################################################################


echo -e "Content-type: text/xml;charset=utf-8\n"
# echo -e "Content-type: text/plain;charset=utf-8\n"
if [[ "POST" = ${REQUEST_METHOD} ]]; then
	read info -n ${CONTENT_LENGTH}
else
	info="${QUERY_STRING}"
fi

for str in ${info//&/ }; do
	key=$(echo ${str%%=*})
	value=$(echo ${str##*=})
	case "${key}" in
		"shoutcast" )		#设备管理
			sh "/srv/sh/app_shoutcast.sh" "${value}" "${info}"
			exit 0
		;;
	esac
done
# alias urldecode='sed "s@+@ @g;s@%@\\\\x@g" | xargs -0 printf "%b"'
# query=$(echo "${info}" | urldecode)
# for str in ${query//&/ }		#使用&进行分割
# do
# 	key=$(echo ${str%%=*})
# 	value=$(echo ${str##*=})
# 	case "${key}" in
# 		"shoutcast" )		#设备管理
# 			sh "/srv/sh/app_shoutcast.sh" $(echo "")
# 			return 0
# 		;;
# 	esac
# done