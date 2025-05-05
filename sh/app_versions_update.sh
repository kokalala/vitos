####################################################################
# 在后台进行固件的下载和更新
# 0：错误；1：完成；2：执行中
####################################################################

echo "2 download start ${$}"

. /srv/sh/app_versions.sh
rm -rf "${vitos_update_sh_log}"
rm -rf "${vitos_update_versions_backups}"
rm -rf "${vitos_update_kill_download}"
rm -rf "/tmp/vitos_log_firmware_update_tar.log"
rm -rf "/tmp/vitos_log_firmware_update_sh_stderr.log"

json=$(vitos_saos_versions_json)
if [[ 0 -ne $? ]]; then     #Json信息获取失败
    echo "0 info 601"
    exit
fi
version=$(vitos_saos_versions_server "${json}")
if [[ 0 -ne $? ]]; then     #没拿到最新版本
    echo "0 info 602"
    exit
fi
echo "2 download version ${version}"
upgrade=$(vitos_saos_versions_compare "${version}" $(vitos_saos_versions_local))
if [[ 1 -ne $? ]]; then     #版本过低不需要升级
    echo "0 info 604"
    exit
fi

if [[ -e ${vitos_update_versions_new} ]]; then
    version_new=$(cat ${vitos_update_versions_new})
    if [ "$version"x = "$version_new"x ]; then
        echo "1 end $version_new"
        exit
    fi
fi

url=$(vitos_saos_versions_link "${json}")
if [[ 0 -ne $? ]]; then      #没拿到下载链接
    echo "0 info 603"
    exit
fi

echo "{\"thunder_version${json#*thunder_version}" > "${vitos_update_versions_backups}"

file=${url##*/}
file=${file%%.tar.bz2*}

TMPDIR="/mnt/vitos-update"
# TMPDIR="/media/sdc1/vitos-update"
if [[ -e ${TMPDIR} ]]; then
    rm -rf ${TMPDIR}
fi
mkdir -p ${TMPDIR}

echo "2 download mktemp ${TMPDIR}"

nohup thunder_download "${url}" "${TMPDIR}/$file" "${TMPDIR}/download.log" "${vitos_update_kill_download}" > "${TMPDIR}/download_nohup.log" &

while (true)
do
    sleep 1s
    msg=$(tail -n 1 ${TMPDIR}/download.log)
    if [ "$msg"x = "download ok"x ]; then
        logmsg="download"
        break
    elif [ "$msg"x = "download kill"x ]; then       #用户取消下载使用不一样的标识
        echo "0 download kill"
        rm -Rf $TMPDIR
        exit
    elif [ "$msg"x = "download url $url"x ]; then
        logmsg="download url $url"
    elif [[ "$msg" =~ ^"download progress" ]]; then
        logmsg=$msg
    else
        echo "0 download"
        cp ${TMPDIR}/download.log /tmp/vitos_log_firmware_download_faild.log
        rm -Rf $TMPDIR
        exit
    fi
    if [[ ${logmsg_last} != ${logmsg} ]]; then
        logmsg_last="${logmsg}"
        echo "2 $logmsg"
    fi
done

rm -f ${vitos_update_kill_download}
echo "2 utar"

cd $TMPDIR
tar -xjvf $file > "/tmp/vitos_log_firmware_update_tar.log" 2>&1
if [[ 0 -eq $? ]]; then
    echo "2 utar finish"
else 
    echo "0 utar"
    rm -Rf $TMPDIR
    exit
fi

cd $file
sh update.sh -l "${vitos_update_sh_log}" 2> "/tmp/vitos_log_firmware_update_sh_stderr.log" | grep -E ^"[0-9]+" 

rm -Rf $TMPDIR
result=$(tail -n 1 "${vitos_update_sh_log}")
if [ "$result"x = "1 update firmware"x ] ;then

    echo "$version" > "${vitos_update_versions_new}"

    echo "1 end $version"
else
    echo "0 end $version"

fi
