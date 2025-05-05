####################################################################
# Sky Luo
# 20190329
# 更新固件
# -u 下载的URL
# -v 版本号
# -l 更新log存储位置
# -k 取消下载的脚本存储位置
# sh update.sh -u http://192.168.8.166/archlinux_v1.0.0_20190328.tar.bz2 -v thunder_v1.0.0_20190401 -l /srv/http/update.log -k /srv/http/kill_download.sh
####################################################################

while getopts ":u:v:l:k:" opt
do
    case $opt in
        u)
        url=$OPTARG
        ;;
        v)
        version=$OPTARG
        ;;
        l)
        log=$OPTARG
        ;;
        k)
        kill_download=$OPTARG
        ;;
    esac
done

version_new=$(sh /srv/http/new_thunder_version.sh)
if [ "$version"x = "$version_new"x ]; then
    echo "1 update $version_new"
cat << EOF > $log
1 update $version_new
EOF
    exit
fi

echo "2 update $version"
cat << EOF > $log
2 update $version
EOF

echo "2 download"
cat << EOF >> $log
2 download
EOF

file=${url##*/}
file=${file%%.tar.bz2*}

TMPDIR=`mktemp -d`
echo $TMPDIR

thunder_download $url $TMPDIR/$file $TMPDIR/download.log $kill_download

while (true)
do
    sleep 1s
    msg=$(tail -n 1 $TMPDIR/download.log)
    if [ "$msg"x = "download ok"x ]; then
        logmsg="download"
        break
    elif [ "$msg"x = "download kill"x ]; then       #用户取消下载使用不一样的标识
        logmsg="download kill"
        echo "0 download kill"
cat << EOF >> $log
0 download kill
EOF
        rm -Rf $TMPDIR
        exit
    elif [ "$msg"x = "download url $url"x ]; then
        logmsg="download url $url"
    elif [[ "$msg" =~ ^"download progress" ]]; then
        logmsg=$msg
    else
        logmsg="download failed"
        echo "0 download"
cat << EOF >> $log
0 download
EOF
        rm -Rf $TMPDIR
        exit
    fi

    echo $logmsg
cat << EOF >> $log
2 $logmsg
EOF

done

echo $logmsg

cat << EOF >> $log
1 $logmsg
EOF

echo "2 utar"

cat << EOF >> $log
2 utar
EOF

cd $TMPDIR

if tar -xjvf $file; then
    echo "1 utar"
cat << EOF >> $log
1 utar
EOF
else 
    echo "0 utar"
cat << EOF >> $log
0 utar
EOF
    rm -Rf $TMPDIR
    exit
fi

cd $file

sh update.sh -l $log

rm -Rf $TMPDIR

result=$(tail -n 1 $log)
if [ "$result"x = "1 update firmware"x ] ;then

cat << EOF > /srv/http/new_thunder_version.sh
echo "$version"
EOF

echo "1 update $version"
cat << EOF >> $log
1 update $version
EOF

else

echo "0 update $version"
cat << EOF >> $log
0 update $version
EOF

fi
