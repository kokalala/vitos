#!/bin/sh
#时区获取、时区设置

##获取当前状态
function vitos_time_status() {

	autontp=$(systemctl is-enabled systemd-timesyncd)
	echo "\"auto\":\"${autontp}\","

	zoneinfo=" \-> ../usr/share/zoneinfo/"
	zone=$(ls -l /etc/localtime 2>/dev/null | grep -Eo "${zoneinfo}.*" | sed -n '1p' | sed "s|${zoneinfo}||")
	if [[ -z "${zone}" ]]; then
		echo "\"zone\":\"UTC\"," #未设置的显示成UTC
	else
		echo "\"zone\":\"${zone}\","
	fi
	date +\"date\":\"%Y-%m-%d\",\"time\":\"%H:%M:%S\" 2>/dev/null
}

#设置时区
function vitos_time_set_zone() {

	if [[ -z $1 ]]; then
		echo "\"status\":1,\"message\":\"101\""
		return 1
	fi
	
	local zone_id=$(echo "${1}" | grep -Po 'zone_id[=]+\K[^&]+')
	if [[ -z ${zone_id} ]]; then
		echo "\"status\":2,\"message\":\"102\""
		return 2
	fi
	
	set=$(timedatectl set-timezone "${zone_id}" 2>&1)
	set_ret=$?
	if [[ 0 -ne $set_ret ]]; then
		echo "\"status\":3,\"message\":\"$set_ret\""
		return 3
	else
	     echo "${zone_id}" > /mnt/settings/time_ctl_timezone.conf
		echo "\"status\":0,\"message\":\"000\","
		vitos_time_status
	fi
}

#获取时区列表
function vitos_time_get_zone_list() {

     timezones=$(timedatectl list-timezones)
     ret=$?
     if [[ 0 -ne $ret ]]; then
		echo "\"status\":1,\"message\":\"$ret\""
		return 1
	else
	     arr=($timezones)
	     len=${#arr[@]}
	     if [[ len > 0 ]]; then
		     i=0
		     for zone in $timezones; do
		         if [[ 0 -eq $i ]]; then
		             i=1
		             echo "\"zone_list\":[\"${zone}\""
		         else
		             echo ",\"${zone}\""
		         fi
		     done
		     echo "]"
		     echo ",\"status\":0,\"message\":\"000\""
	     else
	         echo "\"status\":2,\"message\":\"102\""
	         return 2
	     fi
	fi
}

#验证日期格式 yyyy-MM-dd
function vitos_time_verify_date() {

	if [[ -z "${1}" ]]; then
		echo "100"
		return 1
	fi
	
	echo "${1}" | grep -E -o "^[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}$" > /dev/null
	if [[ $? -ne 0 ]]; then
		echo "101"		#格式不对
		return 1
	fi
	
	d=$(date -d ${1} 2>/dev/null)
	if [[ $? -ne 0 ]]; then
		echo "102"		#日期不对
		return 1
	fi
	
	echo "000"
}

#验证时间格式 hh:mm:ss
function vitos_time_verify_time() {

	if [[ -z "${1}" ]]; then
		echo "100"
		return 1
	fi
	
	echo "${1}" | grep -E -o "^[0-9]{1,2}:[0-9]{1,2}:[0-9]{1,2}$" > /dev/null
	if [[ $? -ne 0 ]]; then
		echo "101"		#格式不对
		return 1
	fi
	
	d=$(date -d ${1} 2>/dev/null)
	if [[ $? -ne 0 ]]; then
		echo "102"		#时间不对
		return 1
	fi
	
	echo "000"
}



#设置日期 yyyy-MM-dd
function vitos_time_set_date() {
	
	if [[ -z $1 ]]; then
		echo "\"status\":1,\"message\":\"101\""
		return 1
	fi
	local date_value=$(echo "${1}" | grep -Po 'date_value[=]+\K[^&]+')
	if [[ -z ${date_value} ]]; then
		echo "\"status\":2,\"message\":\"102\""
		return 2
	fi

	vitos_time_verify_date $date_value > /dev/null 2>&1
	set_ret=$?
	if [[ 0 -ne $set_ret ]]; then
		echo "\"status\":3,\"message\":\"103\""
		return 3
	fi
	
	timedatectl set-ntp false > /dev/null 2>&1
	
	time=$(timedatectl status | grep "Local time:" | awk -n '{ print $5}')
	set=$(timedatectl set-time "${date_value} ${time}" 2>&1)
	set_ret=$?
	if [[ 0 -ne $set_ret ]]; then
		echo "\"status\":4,\"message\":\"$set_ret\""
		return 4
	else
	     timedatectl set-local-rtc 1 > /dev/null 2>&1
	     timedatectl set-local-rtc 0 > /dev/null 2>&1
		echo "\"status\":0,\"message\":\"000\","
		vitos_time_status
	fi

}

#设置时间 hh:mm:ss
function vitos_time_set_time() {
	
	if [[ -z $1 ]]; then
		echo "\"status\":1,\"message\":\"101\""
		return 1
	fi
	
	local time_value=$(echo "${1}" | grep -Po 'time_value[=]+\K[^&]+')
	if [[ -z ${time_value} ]]; then
		echo "\"status\":2,\"message\":\"102\""
		return 2
	fi

	vitos_time_verify_time $time_value > /dev/null 2>&1
	set_ret=$?
	if [[ 0 -ne $set_ret ]]; then
		echo "\"status\":3,\"message\":\"103\""
		return 3
	fi

	timedatectl set-ntp false > /dev/null 2>&1
		
	date=$(timedatectl status | grep "Local time:" | awk -n '{ print $3}')
	set=$(timedatectl set-time "${date} ${time_value}" 2>&1)
	set_ret=$?
	if [[ 0 -ne $set_ret ]]; then
		echo "\"status\":4,\"message\":\"$set_ret\""
		return 4
	else
	     timedatectl set-local-rtc 1 > /dev/null 2>&1
	     timedatectl set-local-rtc 0 > /dev/null 2>&1
		echo "\"status\":0,\"message\":\"000\","
		vitos_time_status
	fi

}


#设置自动 参数:时区
function vitos_time_set_auto() {

     timedatectl set-ntp true > /dev/null 2>&1
     set_ret=$?
     if [[ 0 -ne $set_ret ]]; then
		echo "\"status\":1,\"message\":\"101\""
		return 1
	fi

	set_ret=1
     for((i=1;i<=30;i++)); 
     do
	     status=$(systemctl status systemd-timesyncd | grep "Status:" | grep -Po 'Status[" :]+\K[^ (]+')
		if [[ "Initial" = ${status} ]]; then
		     set_ret=0
			break
		else
		     sleep 1
			continue
		fi
	done

	if [[ 0 -ne $set_ret ]]; then
	     timedatectl set-ntp false > /dev/null 2>&1
		echo "\"status\":2,\"message\":\"$set_ret\""
		return 1
	fi

	echo "enable" > /mnt/settings/time_ctl_mode.conf
	
     timedatectl set-local-rtc 1 > /dev/null 2>&1
	timedatectl set-local-rtc 0 > /dev/null 2>&1
	
	if [[ -z $1 ]]; then
		echo "\"status\":2,\"message\":\"102\""
		return 2
	fi
	local zone_id=$(echo "${1}" | grep -Po 'zone_id[=]+\K[^&]+')
	if [[ -z ${zone_id} ]]; then
		echo "\"status\":3,\"message\":\"103\""
		return 3
	fi
	set=$(timedatectl set-timezone "${zone_id}" 2>&1)
	set_ret=$?
	if [[ 0 -ne $set_ret ]]; then
		echo "\"status\":4,\"message\":\"$set_ret\""
		return 4
	else
	     echo "${zone_id}" > /mnt/settings/time_ctl_timezone.conf
		echo "\"status\":0,\"message\":\"000\","
		vitos_time_status
	fi

}

#设置手动
function vitos_time_set_manual() {

     timedatectl set-ntp false > /dev/null 2>&1
     set_ret=$?
     if [[ 0 -ne $set_ret ]]; then
		echo "\"status\":1,\"message\":\"$set_ret\""
		return 1
	else
	     echo "disable" > /mnt/settings/time_ctl_mode.conf
		echo "\"status\":0,\"message\":\"000\","
		vitos_time_status
	fi
}


#自动更新 参数:时区
function vitos_time_set_auto_update() {

     timedatectl set-ntp false > /dev/null 2>&1
     set_ret=$?
     if [[ 0 -ne $set_ret ]]; then
		echo "\"status\":1,\"message\":\"$set_ret\""
		return 1
	fi
	
     timedatectl set-ntp true > /dev/null 2>&1
     set_ret=$?
     if [[ 0 -ne $set_ret ]]; then
		echo "\"status\":2,\"message\":\"$set_ret\""
		return 1
	fi

	set_ret=1
     for((i=1;i<=30;i++)); 
     do
	     status=$(systemctl status systemd-timesyncd | grep "Status:" | grep -Po 'Status[" :]+\K[^ (]+')
		if [[ "Initial" = ${status} ]]; then
		     set_ret=0
			break
		else
		     sleep 1
			continue
		fi
	done

	if [[ 0 -ne $set_ret ]]; then
		echo "\"status\":2,\"message\":\"$set_ret\""
		return 1
	fi
	
     timedatectl set-local-rtc 1 > /dev/null 2>&1
	timedatectl set-local-rtc 0 > /dev/null 2>&1
	
	if [[ -z $1 ]]; then
		echo "\"status\":2,\"message\":\"102\""
		return 2
	fi
	local zone_id=$(echo "${1}" | grep -Po 'zone_id[=]+\K[^&]+')
	if [[ -z ${zone_id} ]]; then
		echo "\"status\":3,\"message\":\"103\""
		return 3
	fi
	set=$(timedatectl set-timezone "${zone_id}" 2>&1)
	set_ret=$?
	if [[ 0 -ne $set_ret ]]; then
		echo "\"status\":4,\"message\":\"$set_ret\""
		return 4
	else
	     echo "${zone_id}" > /mnt/settings/time_ctl_timezone.conf
		echo "\"status\":0,\"message\":\"000\","
		vitos_time_status
	fi

}
