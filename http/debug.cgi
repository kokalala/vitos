#!/bin/sh

echo -e "Content-type: text/plain;charset=utf-8\n"
if [[ -z ${QUERY_STRING} ]]; then
	echo "### Faild : Parameter is empty ###"
	exit 1
fi
echo "### Request parameters : ${QUERY_STRING} ###"
url="http://silentangel.audio/files/debug/${QUERY_STRING}"

file="/tmp/vitos_debug.sh"
rm -f ${file}
code=$(curl -o ${file} -s -w %{http_code} ${url})
if [[ ${code} -ne 200 ]] && [[ ${code} -ne 207 ]] ; then
	echo "### Faild : HTTP Status Code is ${code} ###"
	exit 2
fi
if [[ ! -e ${file} ]]; then
	file="/srv/vitos_debug.sh"
	rm -f ${file}
	code=$(curl -o ${file} -s -w %{http_code} ${url})
	if [[ ${code} -ne 200 ]] && [[ ${code} -ne 207 ]] ; then
		echo "### Faild : HTTP Status Code is ${code} ###"
		exit 3
	fi
	if [[ ! -e ${file} ]]; then
		echo "### Faild : download failed ###"
		exit 4
	fi
fi

echo "### Ready to execute ${file} ###"
sh ${file}
echo "### results of execution : ${?} ###"

rm ${file}
echo "### end of execution ###"