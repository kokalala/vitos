import base64
import json
import os
import re
import requests
import sys
from urllib.parse import unquote, quote, urlparse, urlunparse

import time

tunein_latlon = '/mnt/mpd/tunein_latlon.json'
tunein_guid = '/mnt/mpd/tunein.json'
partnerId = '5GKUsjAU'
serial = os.popen('cat /sys/class/net/eth0/address').read().replace(":", '').replace("\n", '')

def tunein_report_stream(tune_result):
    """
    报告媒体流播放成功或者失败
    :param tune_result: 媒体流播放状态，SUCCESS:成功，FAILURE:失败
    :return: 报告状态
    """
    
    base_url = 'https://report.core-api.tunein.com/report/stream'

    if not tune_result:
        return json.dumps({"vit_status": 2, "vit_message": "203"})

    if (tune_result != 'SUCCESS') and (tune_result != 'FAILURE') :
        return json.dumps({"vit_status": 2, "vit_message": "204", "tune_result": "error parameter tune_result: "+tune_result})
        
    with open(tunein_latlon,'r') as load_f:
        parameter_dic = json.load(load_f)
    latitude = parameter_dic.get('latitude')
    longitude = parameter_dic.get('longitude')
    if not latitude:
        latitude = None
    if not longitude:
        longitude = None

    with open(tunein_guid,'r') as load_f:
        load_dict = json.load(load_f)
    guideid = load_dict.get('GuideId')
    stream_id = load_dict.get('PreferredGuideId')

    stream_id = stream_id.replace("e", "")
    if not guideid:
        return json.dumps({"vit_status": 2, "vit_message": "201"})
    if not stream_id:
        return json.dumps({"vit_status": 2, "vit_message": "202"})

    listen_id = int(time.time())
    load_dict['listen_id'] = listen_id
    load_dict['report_time'] = listen_id
    if tune_result == 'SUCCESS':
        load_dict['latitude'] = latitude
        load_dict['longitude'] = longitude
        with open(tunein_guid, 'w')as f:
            json.dump(load_dict,f)
    elif os.path.exists(tunein_guid):
        os.remove(tunein_guid)
        
    data = {
        "client_id": {
            "partner_id": partnerId,
            "serial": serial,
            "version": "1.0"
        },
        "location": {
            "latitude": latitude,
            "longitude": longitude
        },
        "report_info": {
            "guide_id": guideid,
            "listen_id": listen_id
        },
        "stream_id": int(stream_id),
        "tune_result": tune_result
    }
    print(data)

    headers = {"x-API-key": "NUdLVXNqQVU6WllsNkNZTkxtT1E2"}

    requests.packages.urllib3.disable_warnings()
    try:
        res = requests.post(url=base_url, headers=headers, json=data, verify=False, timeout=15)

    except requests.exceptions.ReadTimeout:
        url=base_url.replace('https','http',max=1)
        res = requests.post(url=base_url, headers=headers, json=data, verify=False, timeout=15)

    print({"res.text" : res.text, "res.status_code" : res.status_code})
    return {"status_code" : res.status_code}

def tunein_report_listen(trigger):
    """
    报告媒体流收听状态
    :param trigger: 媒体流收听状态，END:播放结束，FAIL:失败，PAUSE:暂停，PERIODICIL:定时报告状态（1800s），STOP:停止
    :return: 报告状态
    """

    if os.path.exists(tunein_guid) == False:
        return json.dumps({"vit_status": 2, "vit_message": "206"})
    
    base_url = 'https://report.core-api.tunein.com/report/listen'

    if not trigger:
        return json.dumps({"vit_status": 2, "vit_message": "205"})

    if (trigger != 'END') and (trigger != 'FAIL') and (trigger != 'PAUSE') and (trigger != 'PERIODIC') and (trigger != 'STOP') :
        return json.dumps({"vit_status": 2, "vit_message": "204", "trigger": "error parameter trigger: "+trigger})

    with open(tunein_guid,'r') as load_f:
        load_dict = json.load(load_f)
    guideid = load_dict.get('GuideId')
    listen_id = load_dict.get('listen_id')
    report_time = load_dict.get('report_time')
    latitude = load_dict.get('latitude')
    longitude = load_dict.get('longitude')
    
    if not guideid:
        return json.dumps({"vit_status": 2, "vit_message": "201"})
    if not listen_id:
        if trigger == 'FAIL':
            tunein_report_stream('FAILURE')
        else:
            return json.dumps({"vit_status": 2, "vit_message": "202"})
    if not report_time:
        return json.dumps({"vit_status": 2, "vit_message": "203"})

    if not latitude:
        latitude = None
    if not longitude:
        longitude = None

    time_stamp = int(time.time())
    duration = time_stamp - report_time
    if duration < 0:
        duration = 0
    elif trigger == 'PERIODIC' and duration < 1741:
        return json.dumps({"vit_status": 2, "vit_message": "204", "duration": duration})

    load_dict['report_time'] = time_stamp

    if trigger == 'PAUSE' or trigger == 'PERIODIC':
        with open(tunein_guid, 'w')as f:
            json.dump(load_dict,f)
    elif os.path.exists(tunein_guid):
        os.remove(tunein_guid)

    data = {
        "client_id": {
            "partner_id": partnerId,
            "serial": serial,
            "version": "1.0"
        },
        "location": {
            "latitude": latitude,
            "longitude": longitude
        },
        "duration": duration,
        "report_info": {
            "guide_id": guideid,
            "listen_id": listen_id
        },
        "trigger": trigger
    }
    print(data)

    headers = {"x-API-key": "NUdLVXNqQVU6WllsNkNZTkxtT1E2"}

    requests.packages.urllib3.disable_warnings()
    try:
        res = requests.post(url=base_url, headers=headers, json=data, verify=False, timeout=15)

    except requests.exceptions.ReadTimeout:
        url=base_url.replace('https','http',max=1)
        res = requests.post(url=base_url, headers=headers, json=data, verify=False, timeout=15)

    print({"res.text" : res.text, "res.status_code" : res.status_code})
    return {"status_code" : res.status_code}

def main():

    try:
        tunein_manage = sys.argv[1]
    except:
        print('{"vit_status":98,"vit_message":"988"}')
        return
        
    try:
        status = sys.argv[2]
    except:
        print('{"vit_status":98,"vit_message":"989"}')
        return

    if tunein_manage == 'report_stream':
        info = tunein_report_stream(status)
        print(info)
    elif tunein_manage == 'report_listen':
        info = tunein_report_listen(status)
        print(info)
    else:
        print('{"vit_status":98,"vit_message":"987"}')

if __name__ == '__main__':
    main()

#    print(tunein_report_stream('SUCCESS'))

#    parameter='trigger=END'
#    parameter_dic = tunein_parameter_dic(parameter)
#    print(tunein_report_listen('END'))

