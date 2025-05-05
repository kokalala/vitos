
while getopts ":u:i:l:k:" opt
do
    case $opt in
        u)
        url=$OPTARG
        ;;
        i)
        md5=$OPTARG
        ;;
        l)
        log=$OPTARG
        ;;
        k)
        kill_download=$OPTARG
        ;;
    esac
done

echo "2 download"
cat << EOF > $log
2 download
EOF

file=${url##*/}
file=${file%%.tar*}

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

echo "1 "$logmsg

cat << EOF >> $log
1 $logmsg
EOF

cd $TMPDIR

echo "2 check md5"
cat << EOF >> $log
2 check md5
EOF

result=$(md5sum $file)

OLD_IFS="$IFS"
IFS=" "
array=($result)
IFS="$OLD_IFS"
if [ "${array[0]}" = $md5 ]; then
   if [ "${array[1]}" = $file ]; then
     echo "1 check md5"
cat << EOF >> $log
1 check md5
EOF
   else
     echo 0 check md5
cat << EOF >> $log
0 check md5
EOF
     exit
   fi
else
   echo 0 check md5
cat << EOF >> $log
0 check md5
EOF
   exit
fi

echo "2 utar"

cat << EOF >> $log
2 utar
EOF

if tar -xf $file; then
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

echo "2 install"
cat << EOF >> $log
2 install
EOF

if sh install.sh; then
  echo "1 install"
cat << EOF >> $log
1 install
EOF
else
  echo "0 install"
cat << EOF >> $log
0 install
EOF
fi



rm -Rf $TMPDIR
