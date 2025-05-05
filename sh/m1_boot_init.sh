#!/bin/sh

# 开机时运行

#U盘软链创建和挂载监听
nohup sh "/srv/sh/app_usb.sh" "boot_run" > /tmp/vitos_boot_usb_create_link.log  2>&1 &

#nas挂载
nohup sh "/srv/sh/app_smb.sh" "boot_run" > /tmp/vitos_boot_nas_create_link.log  2>&1 &

#监听U盘挂载文件夹的变化
sh "/srv/sh/m1_usb_add_listener.sh"		#这个是常驻任务,所以一定要最后一行运行
