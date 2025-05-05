#!/bin/sh

####################################################################
# Created by wannoo on 2019/07/24
# 网络信息相关 
####################################################################

dhcp_conf="/etc/dhcpcd.conf"		#dhcpcd配置文件存放位置
dhcp_conf_backup="/mnt/settings/dhcpcd.conf"		#备份dhcpcd配置文件存放位置
log_network="/srv/http/network.log"		#网络设置时记录日志
regular_address="([0-9]{1,3}[\.]){3}[0-9]{1,3}[/][0-9]{1,2}"
regular_ip="([0-9]{1,3}[\.]){3}[0-9]{1,3}"

#从dhcp配置表中获取 interface
function dhcp_conf_interface(){
	grep -R "interface eth0" ${dhcp_conf}
	return $?
}

#从dhcp配置表中获取 ip netmask
function dhcp_conf_address(){
	grep -R "static ip_address=" ${dhcp_conf} | grep -E -o "${regular_address}"
	return $?
}

#从dhcp配置表中获取 gateway
function dhcp_conf_gateway(){
	grep -R "static routers=" ${dhcp_conf} | grep -E -o "${regular_ip}"
	return $?
}

#从dhcp配置表中获取 dns
function dhcp_conf_dns(){
	grep -R "static domain_name_servers=" ${dhcp_conf} | grep -E -o "${regular_ip}"
	return $?
}

#数据返回处理成键值对
function to_json(){
	echo "\"$1\":\"$2\""
}

#查看当前何种网络类型;返回值:  0:dhcp ;1:static
function what_type(){
	if [[ ! -e ${dhcp_conf} ]]; then
		return 0
	fi
	dhcp_conf_interface > /dev/null
	if [[ 0 -eq $? ]]; then
		return 1
	fi
	return 0
}

#echo "Type:$type"
function get_type(){
	what_type		#通过判断dhcpcd服务是否运行来确定当前是 DHCP 还是 Static
	[ 0 -eq  $? ] && local type="DHCP" || local type="Static"
	echo "$(to_json type ${type})"
}

#查看当前设备IP;返回值: 192.168.10.250
function what_ip(){
	ifconfig eth0 | awk '{print $2}' | grep -E -o "${regular_ip}"
	return $?
}

#echo "IP Address:$ip_address"
function get_ip_address(){
	echo "$(to_json ip $(what_ip))"
}

#echo "Netmask:$netmask"
function get_netmask(){
	local netmask=`ifconfig eth0 | awk '{print $4}' | grep -E -o "${regular_ip}"`
	echo "$(to_json netmask ${netmask})"
}

#echo "Gateway:$gateway"
function get_gateway(){
	local gateway=`route -n | grep "eth0" | grep "UG" | awk '{print $2}' | grep -E -o "${regular_ip}"`
	echo "$(to_json gateway ${gateway})"
}

#echo "DNS:$dns"
#查询 /etc/resolv.conf 文件中，nameserver开头且第二个单词格式为218.85.152.99的语句,将第一行匹配的第二个单词输出
function get_dns(){
	local dns=`cat /etc/resolv.conf | grep "^nameserver" | awk '{ print $2}' | grep -E -o "${regular_ip}" | sed -n '1p'`
	echo "$(to_json dns ${dns})"
}

#echo "MAC Address:$mac_address"
function get_mac_address(){
	local mac_address=`ifconfig eth0 | grep "ether" | awk '{ print $2}' | tr '[:lower:]' '[:upper:]'`
	echo "$(to_json mac ${mac_address})"
}

#返回设备网络信息
#示例返回:"network":{"type":"DHCP","ip_address":"192.168.10.141","netmask":"255.255.252.0","gateway":"192.168.8.1","dns":"218.85.152.99","mac_address":"F4:B5:20:0C:62:E5"}
function get_network_info(){
	echo -n "\"network\":{$(get_type),$(get_ip_address),$(get_netmask),$(get_gateway),$(get_dns),$(get_mac_address)}"
}

#echo ""network":{"mac":"F4:B5:20:0C:62:E5"}"
function get_network_info_mac(){
	local mac_address=`ifconfig eth0 | grep "ether" | awk '{ print $2}' | tr '[:lower:]' '[:upper:]'`
	echo -n "\"network\":{$(get_mac_address)}"
}

#将信息写入日志
#开头: 0:成功,1:失败,2:进行中   #注:1成功时,倒数第二个参数为最新的ip地址
#第2\3单词是当前进行的步骤
#最后一个参数是时间戳
function to_log(){
	echo -e "$1 ${task_name} $2 `date +%s`" >> "${log_network}"
}

#将网络设置成dhcp
#返回:0:设置成功,需要验证新地址是否可用
#返回:99:没有改变,无需处理
#返回:1:设置失败
#设置成功后返回新的IP地址
function network_set_dhcp(){
	task_name="setting dhcp"
	to_log 2 "ready"
	what_type
	if [ 0 -eq $? ]
	then		#判断为DHCP模式,不进行设置,直接返回成功
		to_log 3 "no change return ip old $(what_ip)"
		echo "609"
		return 99
	fi
	#static设置成dhcpcd
	sed -i '/interface eth0/,$d' ${dhcp_conf}		#删除配置表[interface eth0]后面的参数
	network_setting
	return $?
}

#将网络设置成静态前先验证参数
function network_set_static_verify(){
	return 0
}

#将网络设置成static
#传入参数:新的网络参数,示例:ip=192.168.10.122&netmask=255.255.252.0&gateway=192.168.8.1&dns=218.85.152.99
#设置成功后返回新的IP地址
function network_set_static(){
	task_name="setting static"
	to_log 2 "ready"
	#解析要设置的参数
	. "/srv/sh/app_network_verify.sh" > /dev/null
	ip_new=$(verify_ip $(echo "${1}" | grep -Po 'ip[=]+\K[^&]+'))
	if [[ 0 -ne $? ]]; then		#ip验证出错,直接返回错误
		to_log 0 "verify ip error code[${ip_new}]"
		echo "${ip_new}"
		return 1
	fi
	netmask_new=$(verify_netmask $(echo "${1}" | grep -Po 'netmask[=]+\K[^&]+'))
	if [[ 0 -ne $? ]];then		#netmask验证出错,直接返回错误
		to_log 0 "verify netmask error code[${netmask_new}]"
		echo "${netmask_new}"
		return 1
	fi
	netmask_code_new=$(verify_netmask_analysi ${netmask_new})
	if [[ 0 -ne $? ]];then		#netmask转成数字出错,直接返回错误
		to_log 0 "verify netmask code error code[${netmask_code_new}]"
		echo "${netmask_code_new}"
		return 1
	fi
	gateway_new=$(verify_gateway $(echo "${1}" | grep -Po 'gateway[=]+\K[^&]+'))
	if [[ 0 -ne $? ]];then		#gateway验证出错,直接返回错误
		to_log 0 "verify gateway error code[${gateway_new}]"
		echo "${gateway_new}"
		return 1
	fi
	dns_new=$(verify_dns $(echo "${1}" | grep -Po 'dns[=]+\K[^&]+'))
	if [[ 0 -ne $? ]];then		#dns为空,直接返回错误
		to_log 0 "verify dns error code[${dns_new}]"
		echo "${dns_new}"
		return 1
	fi
	local arr_ip=(${ip_new//./ })		#IP地址转为数组
	local arr_nm=(${netmask_new//./ })		#netmask转数组
	local arr_nw=($((${arr_ip[0]}&${arr_nm[0]})) $((${arr_ip[1]}&${arr_nm[1]})) $((${arr_ip[2]}&${arr_nm[2]})) $((${arr_ip[3]}&${arr_nm[3]})));	
	#arrNetwork 示例输出192.168.8.0
	if [[ ${arr_ip[0]} -eq ${arr_nw[0]} ]] && [[ ${arr_ip[1]} -eq ${arr_nw[1]} ]] && [[ ${arr_ip[2]} -eq ${arr_nw[2]} ]] && [[ ${arr_ip[3]} -eq ${arr_nw[3]} ]]; then
		echo "501"
		return 1
	fi
	local arr_wc=($((${arr_nm[0]}^255)) $((${arr_nm[1]}^255)) $((${arr_nm[2]}^255)) $((${arr_nm[3]}^255)))
	#arrWildcard 示例输出0.0.3.255
	local arr_bc=($((${arr_nw[0]}+${arr_wc[0]})) $((${arr_nw[1]}+${arr_wc[1]})) $((${arr_nw[2]}+${arr_wc[2]})) $((${arr_nw[3]}+${arr_wc[3]})))
	#arrBroadcast 示例输出192.168.11.255
	if [[ ${arr_ip[0]} -eq ${arr_bc[0]} ]] && [[ ${arr_ip[1]} -eq ${arr_bc[1]} ]] && [[ ${arr_ip[2]} -eq ${arr_bc[2]} ]] && [[ ${arr_ip[3]} -eq ${arr_bc[3]} ]]; then
		echo "502"
		return 1
	fi
	local arr_gw=(${gateway_new//./ })		#IP地址转为数组
	if [[ ${arr_gw[0]} -eq ${arr_nw[0]} ]] && [[ ${arr_gw[1]} -eq ${arr_nw[1]} ]] && [[ ${arr_gw[2]} -eq ${arr_nw[2]} ]] && [[ ${arr_gw[3]} -eq ${arr_nw[3]} ]]; then
		echo "503"
		return 1
	fi
	if [[ ${arr_gw[0]} -eq ${arr_bc[0]} ]] && [[ ${arr_gw[1]} -eq ${arr_bc[1]} ]] && [[ ${arr_gw[2]} -eq ${arr_bc[2]} ]] && [[ ${arr_gw[3]} -eq ${arr_bc[3]} ]]; then
		echo "504"
		return 1
	fi
	local l_gw=$(($(($((${arr_gw[0]}*256+${arr_gw[1]}))*256+${arr_gw[2]}))*256+${arr_gw[3]}))
	local l_nw=$(($(($((${arr_nw[0]}*256+${arr_nw[1]}))*256+${arr_nw[2]}))*256+${arr_nw[3]}))
	local l_bc=$(($(($((${arr_bc[0]}*256+${arr_bc[1]}))*256+${arr_bc[2]}))*256+${arr_bc[3]}))
	#示例输出 "3232237569 === 3232237568 === 3232238591"
	if [[ l_gw -le l_nw ]] || [[ l_gw -ge l_bc ]]; then
		echo "505"
		return 1
	fi

	local bc_new="${arr_bc[0]}.${arr_bc[1]}.${arr_bc[2]}.${arr_bc[3]}"
	local bc_old=$(ifconfig eth0 | grep " broadcast "  | sed -n '1p' | awk '{print $NF}')
	if [[ -n ${bc_old} ]] && [[ ${bc_new} != ${bc_old} ]]; then
		# echo "${bc_old}==509==${bc_new}"
		echo "509"
		return 1
	fi
	
	to_log 2 "ready parameter: address:${ip_new}/${netmask_code_new} ,gateway:${gateway_new} ,dns:${dns_new}"		#将修改参数记录到日志
	#判断IP是否被使用
	if [[ -z $(ip address show dev eth0 | grep "${ip_new}") ]];then		#判断要设置的IP没有被自己使用
		local curl_test=`curl -m 1 ${ip_new} 2>&1`		#没安装ping,就使用这个
		local user_mac=`arp ${ip_new} | grep "${ip_new}" | grep -E -o "([0-9a-fA-F]{2})(([/\s:][0-9a-fA-F]{2}){5})"`
		if [[ -n ${user_mac} ]];then		#判断要设置的IP没有被别的设备使用
			to_log 0 "the ip[${ip_new}] is user by mac[${user_mac}]"
			echo "${user_mac}"
			return 88
		else
			to_log 2 "the ip[${ip_new}] no found user by other device"
		fi
	fi

	what_type
	if [[ 0 -ne $? ]];then		#判断网络类型:原先是静态
		to_log 2 "is static prepare to set static"
		local address_old=$(dhcp_conf_address)
		local gateway_old=$(dhcp_conf_gateway)
		local dns_old=$(dhcp_conf_dns)
		if [[ "${ip_new}/${netmask_code_new}" == ${address_old} ]] && [[ ${gateway_new} == ${gateway_old} ]] && [[ ${dns_new} == ${dns_old} ]]
		then		#判断提交的内容和旧的一致,不修改,直接返回
			to_log 3 "static to static but no change parameter ${ip_new}"
			echo "609"
			return 99
		fi
		sed -i '/interface eth0/,$d' ${dhcp_conf}		#删除配置表[interface eth0]后面的参数
	else		#这边是为了防止用户没有修改过ip,settings文件夹没有备份文件,可能引起设置回退失败
		if [[ ! -e ${dhcp_conf_backup} ]]; then
			mkdir -p /mnt/settings/
			cp "${dhcp_conf}" "${dhcp_conf_backup}"		#将eth0配置文件复制到/mnt/settings/文件夹里备份
		fi
	fi
	#写入新的配置信息
	local add_info="static ip_address=${ip_new}/${netmask_code_new}\nstatic routers=${gateway_new}\nstatic domain_name_servers=${dns_new}"
	write=$(2>&1 echo -e "interface eth0\n${add_info}" >> "${dhcp_conf}")
	local write_result=$?
	if [[ 0 -ne ${write_result} ]];then		#文件写入异常
		to_log 3 "write eth0 config faild code[${write_result}] message[$write]"
		echo "601"
		return ${write_result}
	fi
	network_setting
	return $?
}

#从DHCP状态中获取IP地址，当前设置为dhcp时获取
function what_dhcp_ip(){
	dhcp_status=`systemctl status dhcpcd.service`
	local dhcp_status_result=$?
	if [[ 0 -ne ${dhcp_status_result} ]];then		#dhcp没有开启
		to_log 2 "dhcpcd status is ${dhcp_status_result}"
		return 1
	fi
	local address_dhcp_conf=$(dhcp_conf_address)
	if [[ -n ${address_dhcp_conf} ]]; then		#从配置表获取类似192.168.10.141/22的IP地址
		to_log 2 "get address[${address_dhcp_conf}] in [dhcp config]"
		echo "${address_dhcp_conf}"
		return 0
	fi
	local address_dhcp_using=`echo "${dhcp_status}" | grep "eth0" | grep "using static address" | awk -n '{ print $NF}' | grep -E -o "${regular_address}" | sed -n '1p'`
	if [[ -n ${address_dhcp_using} ]];then		#在dhcpcd的status中获取类似192.168.10.141/22的IP地址
		to_log 2 "get address[${address_dhcp_using}] by [using static address] in [dhcp status]"
		echo ${address_dhcp_using}
		return 0
	fi
	local address_dhcp_probing=`echo "${dhcp_status}" | grep "eth0" | grep "probing address" | awk -n '{ print $NF}' | grep -E -o "${regular_address}" | sed -n '1p'`
	if [[ -n ${address_dhcp_probing} ]];then		#在dhcpcd的status中获取类似192.168.10.141/22的IP地址
		to_log 2 "get address[${address_dhcp_probing}] by [probing address] in [dhcp status]"
		echo ${address_dhcp_probing}
		return 0
	fi
	local ip_dhcp_rebinding=`echo "${dhcp_status}" | grep "eth0" | grep "rebinding lease of" | awk -n '{ print $NF}' | grep -E -o "${regular_ip}" | sed -n '1p'`
	if [[ -n ${ip_dhcp_rebinding} ]];then		#在dhcpcd的status中获取类似192.168.10.141的IP地址
		to_log 2 "get ip[${ip_dhcp_rebinding}] by [rebinding lease of] in [dhcp status]"
		echo ${ip_dhcp_rebinding}
		return 0
	fi
	to_log 2 "dhcp_conf:\n$(tail -n 5 ${dhcp_conf})"
	to_log 2 "without address in dhcp_conf"
	to_log 2 "dhcp_status:\n${dhcp_status}"
	to_log 2 "without address or ip in dhcp_status"
	return 2
}

#重启dhcpcd服务，并检查ip是否正常设置上去
function network_setting(){
	dhcp_restart=`systemctl restart dhcpcd.service`
	local dhcp_restart_result=$?
	if [[ 0 -eq $dhcp_restart_result ]]; then
		ip link set eth0 down > /dev/null
		sleep 1		#重启网卡
		ip link set eth0 up > /dev/null
		#DHCP服务有正常启动,底下操作为查询新地址,返回给web端
		local i=0 
		while ((i <10))  
		do		#因为网卡刚启动,没法马上拿到新的ip,所以10秒内循环查询
			to_log 2 "when[${i}] ready to check whether address in iproute2"
			address_dhcp=$(what_dhcp_ip)
			if [[ 0 -eq $? ]];then		#有从dhcp状态里拿到新地址
				local ip_show=$(ip address show dev eth0)
				if [[ -n $(echo "${ip_show}" | grep "${address_dhcp}") ]];then
					local address_is_full=$(echo "${address_dhcp}" | grep -E -o "${regular_address}")
					if [[ -n ${address_is_full} ]]; then
						to_log 2 "address is full ${address_dhcp}"
						to_log 1 "return dhcp ip ${address_dhcp%/*}"
						echo "${address_dhcp%/*}"
					else
						to_log 1 "return dhcp ip ${ip_dhcp}"
						echo "${address_dhcp}"
					fi
					sh /srv/sh/app_smb.sh net_modify_run > /tmp/t_smb_net_modify_run 2>&1
					return 0
				fi
				to_log 2 "[dev eth0]:\n${ip_show}"
				to_log 2 "without address[${address_dhcp}] in [dev eth0]"
			fi
			((i++))     #累加
			sleep 1     #休眠一秒
		done
		to_log 0 "No new address was obtained"
		echo "602"		#Failed to get ip address from DHCP server. Please check if DHCP server is working.
	else		#返回值不为0,DHCP服务没有正常开启,返回设置失败
		to_log 2 "code[${dhcp_restart_result}] ;message:${dhcp_restart}"
		to_log 0 "faild to restart dhcp"
		echo "603"		#Failed to run DHCP client.[${dhcp_restart_result}]
	fi
	cp "${dhcp_conf_backup}" "${dhcp_conf}" >> ${log_network}		#将/mnt/settings/文件夹里里的备份恢复到eth0配置文件
	systemctl restart dhcpcd.service >> ${log_network}
	to_log 0 "ending"
	return 1
}


#删除ip addr 里面的其他ip地址
#参数:$1:要保留的IP地址;
#参数:$2:为空时格式类似192.168.10.141/22,不为空时地址格式类似:192.168.10.141
function delete_other_ip(){
	if [[ -z $1 ]]; then
		to_log 2 "ready to remove other ip but with an empty argument"
		return 2
	fi
	local ip_show=$(ip address show dev eth0)
	if [[ -n $(echo "${ip_show}" | grep "${1}") ]]
	then		#在ip add信息里找到需要保留的IP地址,删除其他IP地址
		local address_is_full=`echo "${1}" | grep -E -o "${regular_address}"`
		[[ -n ${address_is_full} ]] && local regular="${regular_address}" || local regular="${regular_ip}"		
		to_log 2 "continue to have ip[${1}] and ready to remove other ip by regular[${regular}]"
		local ip_all=`echo "${ip_show}" | grep "inet" | awk '{print $2}' | grep -E -o "${regular}"`
		for ip in ${ip_all}
		do		#查询ip addr 里所有类似:192.168.10.141/22 或 类似:192.168.10.141 的address
			if [[ "${ip}" != "${1}" ]];then		#循环删除其他IP
				echo $(ip address del "${ip}" dev eth0 2>&1) >> ${log_network}
				to_log 2 "delete ip[${ip}]"
		    fi
		done
		if [[ -n ${address_is_full} ]]; then
			echo "${address_is_full%/*}"
		else
			echo "${1}"
		fi
		return 0
	fi
	to_log 2 "without ip[${1}] in ${ip_show}"
	return 1
}

#设置DHCP成功后,网页端测试连接成功,保存配置到备份文件,删除旧的IP
function network_set_succeed(){
	task_name="success network"
	to_log 2 "ready"
	cp "${dhcp_conf}" "${dhcp_conf_backup}"		#将eth0配置文件复制到/mnt/settings/文件夹里备份
	network_ending "${1}"
	return $?
}

#网络设置后,无法连接新地址,默认出错:恢复配置表,删除其他地址
function network_set_faild(){
	task_name="rollback network"
	to_log 2 "ready"
	cp "${dhcp_conf_backup}" "${dhcp_conf}"		#将/mnt/settings/文件夹里里的备份恢复到eth0配置文件
	network_ending "${1}"
	return $?
}

#删除其他ip
function network_ending(){
	address_dhcp=$(what_dhcp_ip)
	if [[ 0 -eq $? ]];then
		if [[ -n ${1} ]] && [[ -n $(echo "$address_dhcp" | grep "${1}") ]]; then
			ip_only=$(delete_other_ip "${address_dhcp}")
			if [[ 0 -eq $? ]];then
				to_log 3 "only save ip ${1}"
				echo "${1}"
				return 0
			fi
		fi
	fi
	to_log 3 "ending"
	echo "End of network setting"
	return 1
}

#传入参数为当前请求的IP地址
#检查网络设置日志文件，获取日志文件最后一句语句：
#第一个单词:0:失败,1:网络设置成功,待测试;2:进行中;3:测试连接后任务执行完成
#第二三个单词:setting dhcp:开始设置dhcp;
#第二三个单词:setting static:开始设置静态;
#第二三个单词:success network:网络设置成功操作;
#第二三个单词:rollback network:网络设置失败操作；
#最后一个单词:时间戳
#当状态为1时,倒数第二个单词为最新的ip地址。
function inspect_network_log(){
	if [ ! -e ${log_network} ]  
	then		#不存在网络设置日志文件
		return 1
	fi
	if [[ -z $1 ]]
	then		#传入的当前网页请求地址为空
		return 2
	fi
	local last_column=`tail -n 1 ${log_network}`		#最后一行
	if [[ $last_column =~ ^1.* ]]
	then		#1开头,上次操作成功
		local ip_log=`echo ${last_column} | awk  '{print $(NF-1)}'`		#日志文件拿到的ip地址,倒数第二个单词
		if [[ -z ${ip_log} ]]
		then		#日志里的地址为空
			return 3
		fi
		if [[ ${ip_log} == $1 ]]  
		then		#请求的地址和日志里的ip地址相同时，直接执行对应任务，删除旧地址。
			if [[ ${last_column} =~ "1 setting dhcp" ]] || [[ ${last_column} =~ "1 setting static" ]]
			then
				network_set_succeed $1
				return 4
			fi
		else		#请求的地址和日志里待测试的ip地址不一致时，返回地址和类型给web去测试连接，同时显示对话框给用户查看。
			if [[ ${last_column} =~ "1 setting dhcp" ]]
			then
				echo -n "${ip_log}"
				return 0
			elif [[ ${last_column} =~ "1 setting static" ]]
			then
				echo -n "${ip_log}"
				return 0
			fi
		fi	
	fi
	return 6
}
