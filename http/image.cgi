#!/bin/sh

####################################################################
# Created by wannoo on 2021/8/8
# 根据路径输出图片
# 如果不是图片或者路径为文件夹就输出文件夹内名称为cover的图片（后缀：jpg、jpeg、.png、bmp），没有匹配名称就输出拿到的第一张图片
####################################################################

alias urldecode='sed "s@+@ @g;s@%@\\\\x@g" | xargs -0 printf "%b"'
path=$(echo ${QUERY_STRING} | urldecode)	#http携带的参数

if [[ -n $(echo "${path}" | grep "^nas/\|^usb/") ]]; then	#为MPD的相对路径补充绝对路径
	path="/mnt/mpd/music/${path}"
fi

if [[ -e "${path}" ]]; then
	type="$(file --mime-type "${path}" -b |grep ^"image/")"	#路径为图片直接输出
	if [[ -n "${type}" ]]; then
		echo -e "Content-type:${type}\n"
		cat "${path}"
		exit 0
	fi
fi

if [[ -d "${path}" ]]; then
	dir="${path}"
else
	dir="$(dirname "${path}")"	#获取文件的父文件夹
	if [[ ! -d "${dir}" ]]; then
		echo -e "Content-type: text/plain;charset=utf-8\n"
		echo "${dir} Folder does not exist"
		exit 1
	fi
fi

file_all=$(ls -1 "${dir}" | grep -i ".jpg$\|.jpeg$\|.png$\|.bmp$")	#只获取指定后缀的文件

image="${dir}/$(echo "${file_all}" | grep -i "^cover.jpg$" | sed -n '1p')"
if [[ -n "${image}" ]]; then
	type="$(file --mime-type "${image}" -b |grep ^"image/")"
	if [[ -n "${type}" ]]; then
		echo -e "Content-type:${type}\n"
		cat "${image}"
		exit 0
	fi
fi
image="${dir}/$(echo "${file_all}" | grep -i "^cover.jpeg$" | sed -n '1p')"
if [[ -n "${image}" ]]; then
	type="$(file --mime-type "${image}" -b |grep ^"image/")"
	if [[ -n "${type}" ]]; then
		echo -e "Content-type:${type}\n"
		cat "${image}"
		exit 0
	fi
fi
image="${dir}/$(echo "${file_all}" | grep -i "^cover.png$" | sed -n '1p')"
if [[ -n "${image}" ]]; then
	type="$(file --mime-type "${image}" -b |grep ^"image/")"
	if [[ -n "${type}" ]]; then
		echo -e "Content-type:${type}\n"
		cat "${image}"
		exit 0
	fi
fi
image="${dir}/$(echo "${file_all}" | grep -i "^cover.bmp$" | sed -n '1p')"
if [[ -n "${image}" ]]; then
	type="$(file --mime-type "${image}" -b |grep ^"image/")"
	if [[ -n "${type}" ]]; then
		echo -e "Content-type:${type}\n"
		cat "${image}"
		exit 0
	fi
fi

IFS_old=$IFS
IFS=$'\n'
for file in ${file_all}; do
	image="${dir}/${file}"
	type="$(file --mime-type "${image}" -b |grep ^"image/")"
	if [[ -n "${type}" ]]; then
		echo -e "Content-type:${type}\n"
		cat "${image}"
		exit 0
	fi
done
IFS=$IFS_old

echo -e "Content-type: text/plain;charset=utf-8\n"
echo "${dir} There are no pictures in the folder"
