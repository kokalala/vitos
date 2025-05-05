import base64
import json
import os
import re
import requests
import sys
from urllib.parse import unquote, quote, urlparse, urlunparse

import time

tunein_m3u8_path = "/tmp/vitos_tunein_list.m3u8"
app_station_info = '/mnt/mpd/app_song_info'
info_path = '/mnt/settings/token_info.txt'
partnerId = '5GKUsjAU'
serial = os.popen('cat /sys/class/net/eth0/address').read().replace(":", '').replace("\n", '')
vit_prefix = "http://online.silentangel.audio/tunein?url="

language_dic = {
    '1': 'zh-tw,zh-hk,zh-cn;q=0.9,en;q=0.7',
    '2': 'zh-cn;q=0.9,en;q=0.8',
    '3': 'ja;q=0.9,en;q=0.8',
    '4': 'de;q=0.9,en;q=0.8',
    '5': 'ko;q=0.9,en;q=0.8',
    '6': 'es;q=0.9,en;q=0.8',
    '7': 'nl;q=0.9,en;q=0.8',
    '8': 'en-us;q=0.7,en;q=0.9'
}
def tunein_request(url):
    requests.packages.urllib3.disable_warnings()
    try:
        res = requests.get(url=url, headers=headers, verify=False, timeout=15)

    except requests.exceptions.ReadTimeout:
        url=url.replace('https','http',max=1)
        res = requests.get(url=url, headers=headers, verify=False, timeout=15)
    return res

def structure_url(base_url, parameter_dic={}):
    if username:
        base_url += f'?partnerId={partnerId}&version=1.0&username={username}&serial={serial}'
    else:
        base_url += f'?partnerId={partnerId}&version=1.0&serial={serial}'

    for key, value in parameter_dic.items():
        base_url += f"&{key}={value}"
        
    with open("/srv/py/tunein/tunein_url.txt", 'w')as f:
        f.write(base_url)
            
    return base_url

def get_username(result):
    result = result.split('.')[1]
    while True:
        try:
            temp = base64.b64decode(result)
            temp = temp.decode(errors='ignore')
            break
        except:
            result += '='
    username = re.findall('"username":"(.+)","data', temp)
    return username


def get_headers_and_username(parameter_dic):
    """语言设置：
        默认是英语
        1:繁中
        2：简中
        3：日语
        4：德语
        5:韩语
        6：西班牙语
        7：荷兰语
        8：英语
    """

    language = parameter_dic.get('language')
    if not language:
        language = 0
    else:
        del parameter_dic['language']

    if language == '1':
        Accept_Language = language_dic['1']
        # Accept_Language ="zh-tw,zh-hk,zh-cn;q=0.9,en;q=0.7"
    elif language == '2':
        Accept_Language = language_dic['2']
        # Accept_Language = "zh-cn;q=0.9,en;q=0.8"
    elif language == '3':
        Accept_Language = language_dic['3']
        # Accept_Language ="ja;q=0.9,en;q=0.8"
    elif language == '4':
        Accept_Language = language_dic['4']
        # Accept_Language = "de;q=0.9,en;q=0.8"
    elif language == '5':
        Accept_Language = language_dic['5']
        # Accept_Language = "ko;q=0.9,en;q=0.8"
    elif language == '6':
        Accept_Language = language_dic['6']
        # Accept_Language = "es;q=0.9,en;q=0.8"
    elif language == '7':
        Accept_Language = language_dic['7']
        # Accept_Language = "nl;q=0.9,en;q=0.8"
    else:
        Accept_Language = language_dic['8']
        # Accept_Language="en-us;q=0.7,en;q=0.9"
    if os.path.exists(info_path):
        with open(info_path) as f:
            tokeninfo = json.load(f)
        username = tokeninfo.get('username')
        expires = tokeninfo.get('expires')
        login_time = tokeninfo.get('now_time')
        now_time = time.time()

        if now_time < login_time + expires:  # 判断token是否过期
            access_token = tokeninfo.get("access_token")  # 没有过期则从文件中提取token
        else:
            refresh_info = json.loads(tunein_refresh_token())  # 过期了则刷新token，获取新的token
            access_token = refresh_info.get('access_token')

        if not access_token:
            username = ''
            headers = {
                "Accept-Language": Accept_Language
            }
        else:
            headers = {
                "Authorization": "Bearer " + access_token,
                "Accept-Language": Accept_Language
            }
    else:
        username = ''
        headers = {
            "Accept-Language": Accept_Language
        }
    return headers, username


def maybe_login():
    if os.path.exists(info_path):
        # 文件存在则表示用户登陆了
        return json.dumps({"islogin": True})
    else:
        state = os.popen('cat /sys/class/net/eth0/address').read().replace(":", '').replace('\n', '')

        data = {
            'islogin': False,
            'login_url': f'https://tunein.com/authorize/?response_type=code&client_id=5GKUsjAU&redirect_uri=http://silentangel.audio/files/saos/tunein&state={state}'
        }
        return json.dumps(data)


def logout():
    info = ''
    skip_tidal = False
    try:
        os.system('mpc playlistdel http://online.silentangel.audio/tunein > /dev/null 2>&1')
        with open(app_station_info, encoding='utf8')as f:
            for line in f:
                if line.startswith('song_begin: ' + vit_prefix):
                    skip_tidal = True
                if skip_tidal:
                    if line.startswith('song_end'):
                        skip_tidal = False
                    continue
                else:
                    info += line
        with open(app_station_info, 'w+', encoding='utf8')as f:
            f.write(info)
    except:
        pass
    if os.path.exists(info_path):
        os.remove(info_path)
        #     os.system('mpc clear > /dev/null 2>&1 ')
        return json.dumps({"vit_status": 0, "vit_message": ""})
    else:
        return json.dumps({"iflogin": False, "message": "not login"})


def tunein_parameter_dic(parameter):
    parameter_dic = {}
    try:
        parameter_list = parameter.split('&')

        for parameter in parameter_list:
            key = unquote(parameter.split('=', 1)[0].strip())
            value = unquote(parameter.split('=', 1)[1].strip())
            parameter_dic[key] = value
        return parameter_dic
    except:
        return 'error'


# -----------------------------------------------------------------------oAuth 2.0 API----------------------------------------------------
def get_token(parameter_dic):
    # parameter_dic = tunein_parameter_dic(parameter)
    # if isinstance(parameter_dic, str):
    # return '200'
    code = parameter_dic.get('code')
    if not code:
        return {"vit_status": 2, "vit_message": "201"}
    state = os.popen('cat /sys/class/net/eth0/address').read().replace(":", '').replace("\n", '')
    url = "https://tunein.com/api/v1/auth/refresh/"
    data = {
        "token_uri": "https://tunein.com/api/v1/auth/refresh/",
        "client_id": "5GKUsjAU",
        "client_secret": "NUdLVXNqQVU6WllsNkNZTkxtT1E2",
        "state": state,
        "version": 2.0,
        "code": code
    }
    requests.packages.urllib3.disable_warnings()
    # 字符串格式
    try:
        # res=tunein_request(url)
        res = requests.post(url=url, json=data, verify=False, timeout=15)
    except:
        try:
            url=url.replace('https','http',1)
            res = requests.post(url=url, json=data, verify=False, timeout=15)
        except:
            return json.dumps({"vit_status": 4, "vit_message": "444"})
    if res.status_code == 200:

        now_time = time.time()
        usname = "".join(get_username(code))
        info = json.loads(res.text)
        info['username'] = usname
        info['now_time'] = now_time
        info = json.dumps(info)
        with open(info_path, 'w+', encoding='utf8', )as f:
            f.write(info)
        return json.dumps({"vit_status": 0, "vit_message": ""})
    else:
        return json.dumps({"vit_status": 4, "vit_message": "445"})


def tunein_refresh_token():
    f = open(info_path, 'r+', encoding='utf8')
    try:
        token_info = json.load(f)
    except:
        f.close()
        return 444  # 文件读取失败。
    refresh_token = token_info.get('refresh_token')
    if not refresh_token:
        f.close()
        return json.dumps({"vit_status": 2, "vit_message": "201"})
    state = os.popen('cat /sys/class/net/eth0/address').read().replace(":", '').replace("\n", '')
    url = 'https://tunein.com/api/v1/auth/refresh/'
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": "5GKUsjAU",
        "client_secret": "NUdLVXNqQVU6WllsNkNZTkxtT1E2",
        "state": state,
        "version": 2.0
    }

    try:
        requests.packages.urllib3.disable_warnings()
        res = requests.post(url=url, json=data, verify=False, timeout=15)
    except:
        f.close()
        if os.path.exists(info_path):
            os.remove(info_path)
        return json.dumps({"vit_status": 4, "vit_message": "444"})

    if res.status_code == 200:
        info = json.loads(res.text)
        token_info['access_token'] = info.get('access_token')
        token_info['refresh_token'] = info.get('refresh_token')
        token_info['expires'] = info.get('expires')
        now_time = time.time()
        token_info['now_time'] = now_time
        f.seek(0)
        f.truncate()
        f.write(json.dumps(token_info))
        f.close()
        info["vit_status"] = 0
        info["vit_message"] = ''
        return json.dumps(info)
    else:
        f.close()
        if os.path.exists(info_path):
            os.remove(info_path)
        
        return json.dumps({"vit_status": 4, "vit_message": "445"})


def tunein_common(parameter_dic):
    url = parameter_dic.get('url')
    if not url:
        return json.dumps({"vit_status": 2, "vit_message": "201"})
    try:
        res = tunein_request(url)
        # requests.packages.urllib3.disable_warnings()
        # res = requests.get(url=unquote(url), headers=headers, verify=False, timeout=15)
    except:
        return json.dumps({"vit_status": 4, "vit_message": "444"})
    info = res.text
    # info = change_item(change_item)
    return info


# --------------------------------------------------------------------Favorites API----------------------------------------------
def get_user_favorite(parameter_dic):
    if username:
        # url=f'https://api.radiotime.com/profiles/me/follows?partnerId={partnerId}&version=1.0&username={username}&serial={serial}'
        base_url = 'https://api.radiotime.com/profiles/me/follows'
        url = structure_url(base_url, parameter_dic)
    else:
        return json.dumps({"vit_status": 2, "vit_message": "201"})
    try:
        res = tunein_request(url)
        # requests.packages.urllib3.disable_warnings()
        # res = requests.get(url=url, headers=headers, verify=False, timeout=15)
    except:
        return json.dumps({"vit_status": 4, "vit_message": "444"})
    favorite_info = res.text
    return favorite_info


def add_or_delete_favorite(parameter_dic):
    login_info = json.loads(maybe_login())
    islogin = login_info.get('islogin')
    if islogin != True:  # 未登陆的用户不能进行收藏和取消收藏的操作
        return json.dumps(login_info)
        # parameter_dic = tunein_parameter_dic(parameter)
        # if isinstance(parameter_dic, str):
        # return '200'
    guideid = parameter_dic.get('guideid')
    if not guideid:
        return {"vit_status": 2, "vit_message": "201"}
    else:
        del parameter_dic['guideid']
    # username=parameter_dic.get('username')
    # if not username:
    #     return {"vit_status":2,"vit_message":"202"}
    action = parameter_dic.get('action')
    if not action:
        return json.dumps({"vit_status": 2, "vit_message": "202"})
    else:
        del parameter_dic['action']
    # if username:
    #     url=f'http://api.radiotime.com/favorites/{guideid}?&partnerId={partnerId}&username={username}&version=1.0&serial={serial}'
    # else:
    #     url=f'http://api.radiotime.com/favorites/{guideid}?&partnerId={partnerId}&version=1.0&serial={serial}'
    # print(url)
    base_url = f'https://api.radiotime.com/favorites/{guideid}'
    url = structure_url(base_url, parameter_dic)

    requests.packages.urllib3.disable_warnings()
    if action == 'add':
        res = requests.post(url=url, headers=headers, verify=False, timeout=15)
        if res.status_code != 200:
            return json.dumps({"vit_status": 4, "vit_message": res.status_code})
        else:
            return json.dumps({"vit_status": 0, "vit_message": ""})
    elif action == 'delete':
        res = requests.delete(url=url, headers=headers, verify=False, timeout=15)
        if res.status_code != 200:
            return json.dumps({"vit_status": 4, "vit_message": res.status_code})
        else:
            return json.dumps({"vit_status": 0, "vit_message": ""})
    else:
        return json.dumps({"vit_status": 3, "vit_message": "303"})


# --------------------------------------------------------------------------Browse API---------------------------------------------------------------------------------------------------------------------------
def beword(parameter_dic):
    # if username:
    #     url=f'http://api.radiotime.com/categories/root?partnerId={partnerId}&username={username}&latlon=22.381754,114.055235&version=1&serial={serial}'
    # else:
    #     url=f'http://api.radiotime.com/categories/root?partnerId={partnerId}&latlon=22.381754,114.055235&version=1&serial={serial}'
    base_url = 'https://api.radiotime.com/categories/root'
    url = structure_url(base_url, parameter_dic)

    try:
        res = tunein_request(url)
        # res = requests.get(url=url, headers=headers, timeout=15)
    except:
        return json.dumps({"vit_status": 4, "vit_message": "444"})
    beword_info = res.text
    return beword_info


def tunein_local_radio(parameter_dic):
    # if username:
    #     url = f'https://api.radiotime.com/categories/local?username={username}&partnerId={partnerId}&version=1.0&serial={serial}'
    #
    # else:
    #     url = f'https://api.radiotime.com/categories/local?partnerId={partnerId}&version=1.0&serial={serial}'
    base_url = 'https://api.radiotime.com/categories/local'
    url = structure_url(base_url, parameter_dic)
    try:
        res = tunein_request(url)
        # requests.packages.urllib3.disable_warnings()
        # res = requests.get(url=url, headers=headers, verify=False, timeout=15)
    except:
        return json.dumps({"vit_status": 4, "vit_message": "444"})
    local_radio_info = res.text
    return local_radio_info


def change_item(info_data):
    info_data = json.loads(info_data)
    items = info_data.get('Items')
    items_dic = {}
    for i in items:
        key = i.get('GuideId')
        items_dic[key] = i
    info_data['Items'] = items_dic
    return json.dumps(info_data)


def tunein_music(parameter_dic):
    # if username:
    #     url = f'https://api.radiotime.com/categories/music?username={username}&partnerId={partnerId}&version=1.0&serial={serial}'
    # else:
    #     url = f'https://api.radiotime.com/categories/music?partnerId={partnerId}&version=1.0&serial={serial}'
    base_url = 'https://api.radiotime.com/categories/music'
    url = structure_url(base_url, parameter_dic)
    try:
        res = tunein_request(url)
#        requests.packages.urllib3.disable_warnings()
#        res = requests.get(url=url, headers=headers, verify=False)
    except:
        return json.dumps({"vit_status": 4, "vit_message": "444"})
    music_info = res.text
    # music_info=change_item(music_info)
    return music_info


def tunein_talk_and_new(parameter_dic):
    # if username:
    #     url = f'https://api.radiotime.com/categories/c57922?username={username}&partnerId={partnerId}&version=1.0&serial={serial}'
    # else:
    #     url = f'https://api.radiotime.com/categories/c57922?partnerId={partnerId}&version=1.0&serial={serial}'
    base_url = 'https://api.radiotime.com/categories/c57922'
    url = structure_url(base_url, parameter_dic)
    try:
        res = tunein_request(url)
        # requests.packages.urllib3.disable_warnings()
        # res = requests.get(url=url, headers=headers, verify=False)
    except:
        return json.dumps({"vit_status": 4, "vit_message": "444"})
    talk_and_new_info = res.text
    # talk_and_new_info =change_item(talk_and_new_info)
    return talk_and_new_info


def tunein_sport(parameter_dic):
    # if username:
    #     url = f'https://api.radiotime.com/categories/sports?username={username}&partnerId={partnerId}&version=1.0&serial={serial}'
    # else:
    #     url = f'https://api.radiotime.com/categories/sports?partnerId={partnerId}&version=1.0&serial={serial}'
    base_url = 'https://api.radiotime.com/categories/sports'
    url = structure_url(base_url, parameter_dic)
    try:
        res = tunein_request(url)
        # requests.packages.urllib3.disable_warnings()
        # res = requests.get(url=url, headers=headers, verify=False)
    except:
        return json.dumps({"vit_status": 4, "vit_message": "444"})
    sports_info = res.text
    # sports_info =change_item(sports_info)
    return sports_info


def tunein_by_location(parameter_dic):
    # if username:
    #     url = f'https://api.radiotime.com/categories/regions?username={username}&partnerId={partnerId}&version=1.0&serial={serial}'
    # else:
    #     url = f'https://api.radiotime.com/categories/regions?partnerId={partnerId}&version=1.0&serial={serial}'
    base_url = 'https://api.radiotime.com/categories/regions'
    url = structure_url(base_url, parameter_dic)
    try:
        res = tunein_request(url)
        # requests.packages.urllib3.disable_warnings()
        # res = requests.get(url=url, headers=headers, verify=False)
    except:
        return json.dumps({"vit_status": 4, "vit_message": "444"})
    location_info = res.text
    return location_info


def tunein_by_languages(parameter_dic):
    # if username:
    #     url = f'https://api.tunein.com/categories/languages?username={username}&partnerId={partnerId}&version=1.0&serial={serial}'
    # else:
    #     url = f'https://api.tunein.com/categories/languages?partnerId={partnerId}&version=1.0&serial={serial}'
    base_url = 'https://api.tunein.com/categories/languages'
    url = structure_url(base_url, parameter_dic)
    try:
        res = tunein_request(url)
        # requests.packages.urllib3.disable_warnings()
        # res = requests.get(url=url, headers=headers, verify=False)
    except:
        return json.dumps({"vit_status": 4, "vit_message": "444"})
    languages_info = res.text
    return languages_info


def tunein_podcasts(parameter_dic):
    # if username:
    #     url = f'https://api.radiotime.com/categories/podcasts?username={username}&partnerId={partnerId}&version=1.0&serial={serial}'
    # else:
    #     url = f'https://api.radiotime.com/categories/podcasts?partnerId={partnerId}&version=1.0&serial={serial}'
    base_url = 'https://api.radiotime.com/categories/podcasts'
    url = structure_url(base_url, parameter_dic)
    try:
        res = tunein_request(url)
        # requests.packages.urllib3.disable_warnings()
        # res = requests.get(url=url, headers=headers, verify=False)
    except:
        return json.dumps({"vit_status": 4, "vit_message": "444"})

    podcasts_info = res.text
    # podcasts_info=change_item(podcasts_info)
    return podcasts_info


# --------------------------------------------------------------------------------------------------------Media API-------------------------------------------------------------------------------------------------
def tunein_media(parameter_dic):
    guideid = parameter_dic.get('guideid')
    if not guideid:
        return json.dumps({"vit_status": 2, "vit_message": "201"})
    # if username:
    #     url=f'http://api.radiotime.com/profiles/{guideid}/media?partnerId={partnerId}&username={username}&version=1.0&serial={serial}'
    # else:
    #     url=f'http://api.radiotime.com/profiles/{guideid}/media?partnerId={partnerId}&version=1.0&serial={serial}'

    base_url = f"https://api.radiotime.com/profiles/{guideid}/media"
    del parameter_dic['guideid']
    url = structure_url(base_url, parameter_dic)
    try:
        res = tunein_request(url)
        # requests.packages.urllib3.disable_warnings()
        # res = requests.get(url=url, headers=headers, verify=False)
    except:
        return json.dumps({"vit_status": 4, "vit_message": "444"})
    media_info = res.text
    return media_info


# ---------------------------------------------------------------------------------------------------Profiles Endpoint------------------------------------------------------------------------------------------
def tunein_profiles_endpoint(parameter_dic):
    # parameter_dic=tunein_parameter_dic(parameter)
    # if isinstance(parameter_dic, str):
    # return '200'
    guideid = parameter_dic.get('guideid')
    if not guideid:
        return json.dumps({"vit_status": 2, "vit_message": "201"})
    # if username:
    #     url=f"https://api.radiotime.com/profiles/{guideid}?partnerId={partnerId}&username={username}&version=1.0&serial={serial}"
    # else:
    #     url=f"https://api.radiotime.com/profiles/{guideid}?partnerId={partnerId}&version=1.0&serial={serial}"
    base_url = f"https://api.radiotime.com/profiles/{guideid}"
    del parameter_dic['guideid']
    url = structure_url(base_url, parameter_dic)
    try:
        # url=f"https://api.radiotime.com/profiles/{guideid}?partnerId={partnerId}&version=1.0"
        res = tunein_request(url)
        # requests.packages.urllib3.disable_warnings()
        # res = requests.get(url=url, verify=False)
    except:
        return json.dumps({"vit_status": 4, "vit_message": "444"})

    profiles_info = res.text
    return profiles_info


# -------------------------------------------------------------------------------------------------Search Endpoint--------------------------------------------------------------------------------------------
def tunein_seach(parameter_dic):
    # 检测必需参数
    query = parameter_dic.get('query')
    if not query:
        return json.dumps({"vit_status": 2, "vit_message": "201"})
    username = parameter_dic.get('username')

    if not username:
        url = f'https://api.radiotime.com/profiles?fulltextsearch=true&query={query}&partnerId={partnerId}&version=1.0&serial={serial}'
    else:
        url = f'https://api.radiotime.com/profiles?fulltextsearch=true&query={query}&partnerId={partnerId}&username={username}&version=1.0&serial={serial}'
    latlon = parameter_dic.get('latlon')
    if latlon:
        url += f'&latlon={latlon}'
    try:
        res = tunein_request(url)
        # requests.packages.urllib3.disable_warnings()
        # res = requests.get(url=url, headers=headers,timeout=7,verify=False)
    except:
        return json.dumps({"vit_status": 4, "vit_message": "444"})
    seach_info = res.text
    return seach_info


# ----------------------------------------------------------------------------------------------------Get users info----------------------------------------------------------------------------------------------
def tunein_get_user_info(parameter_dic):
    if not username:
        return json.dumps({"vit_status": 2, "vit_message": "201"})
    # url=f'https://api.radiotime.com/profiles/me?partnerId={partnerId}&version=1.0&username={username}&serial={serial}'
    base_url = 'https://api.radiotime.com/profiles/me'
    url = structure_url(base_url, parameter_dic)
    try:
        res = tunein_request(url)
        # requests.packages.urllib3.disable_warnings()
        # res = requests.get(url=url, headers=headers, verify=False)
    except:
        return json.dumps({"vit_status": 4, "vit_message": "444"})
    user_info = res.text
    return user_info


# -----------------------------------------------------------------------------------------------------Home API-------------------------------------------------------------------------------------------------


def tunein_home(parameter_dic):
    # if username:
    #     url=f'http://api.radiotime.com/categories/home?username={username}&partnerId={partnerId}&version=1.0&serial={serial}'
    #
    # else:
    #     url=f'http://api.radiotime.com/categories/home?partnerId={partnerId}&version=1.0&serial={serial}'
    base_url = 'https://api.radiotime.com/categories/home'
    url = structure_url(base_url, parameter_dic)
    try:
        requests.packages.urllib3.disable_warnings()
        res = requests.get(url=url, headers=headers, verify=False, timeout=10)
        home_info = res.text
        return home_info

    except requests.exceptions.ReadTimeout:
        try:
            url = url.replace('https', 'http')
            requests.packages.urllib3.disable_warnings()
            res = requests.get(url=url, headers=headers, verify=False, timeout=10)
            home_info = res.text
            return home_info
        except:
            path = '/srv/py/tunein/json'
            for root, dirs, files in os.walk(path):
                # print(root)  # 当前目录路径
                # print(dirs)  # 当前路径下所有子目录
                files_list = files
                language = parameter_dic.get('language')
                if not language:
                    language = '8'
                file_name = language + '.json'
                if file_name not in files_list:
                    file_name = files_list[-1]
                with open(path + '/' + file_name)as f:
                    home_info = f.read()
                return home_info


def tunein_recents(parameter_dic):
    # if not username:
    #     url = f'https://api.radiotime.com/categories/recents?partnerId={partnerId}&version=1.0&serial={serial}'
    # else:
    #     url = f'https://api.radiotime.com/categories/recents?username={username}&partnerId={partnerId}&version=1.0&serial={serial}'
    base_url = 'https://api.radiotime.com/categories/recents'
    url = structure_url(base_url, parameter_dic)
    try:
        # requests.packages.urllib3.disable_warnings()
        # res = requests.get(url=url, headers=headers, verify=False, timeout=15)
        res = tunein_request(url)
    except:
        return json.dumps({"vit_status": 4, "vit_message": "444"})
    recents_info = res.text
    return recents_info


def tunein_trending(parameter_dic):
    # if not username:
    #     url = f'https://api.radiotime.com/categories/trending?partnerId={partnerId}&version=1.0&serial={serial}'
    # else:
    #     url = f'https://api.radiotime.com/categories/trending?username={username}&partnerId={partnerId}&version=1.0&serial={serial}'

    base_url = 'https://api.radiotime.com/categories/trending'
    url = structure_url(base_url, parameter_dic)
    try:
        # requests.packages.urllib3.disable_warnings()
        # res = requests.get(url=url, headers=headers, verify=False, timeout=15)
        res = tunein_request(url)
    except:
        return json.dumps({"vit_status": 4, "vit_message": "444"})
    trending_info = res.text
    return trending_info

# ----------------------------------------------Now Playing API---------------------------------------------------------
def tunein_now_playing(parameter_dic):
    # parameter_dic = tunein_parameter_dic(parameter)
    # if isinstance(parameter_dic, str):
    # return '200'
    guideid = parameter_dic.get('guideid')
    if not guideid:
        return json.dumps({"vit_status": 2, "vit_message": "201"})
    # if not username:
    #     url = f'http://api.radiotime.com/profiles/{guideid}/nowPlaying?partnerId={partnerId}&version=1.0&serial={serial}'
    # else:
    #     url =f'http://api.radiotime.com/profiles/{guideid}/nowPlaying?partnerId={partnerId}&version=1.0&username={username}&serial={serial}'
    base_url = f'https://api.radiotime.com/profiles/{guideid}/nowPlaying'
    del parameter_dic['guideid']
    url = structure_url(base_url, parameter_dic)
    try:
        res = tunein_request(url)
        # requests.packages.urllib3.disable_warnings()
        # res = requests.get(url=url, headers=headers, verify=False, timeout=15)
    except:
        return json.dumps({"vit_status": 4, "vit_message": "444"})
    info = res.text
    return info


# -----------------------------------------------------------------------------------播放相关------------------------------------------------------
def get_play_url(parameter):
    parameter_dic = tunein_parameter_dic(parameter=parameter)
    if isinstance(parameter_dic, str):
        return 'tidal_get_play_url 200'
    track_id = parameter_dic.get('track_id', '')
    if track_id:
        base_url = f'https://api.radiotime.com/profiles/{track_id}/media'
        url = structure_url(base_url, parameter_dic)
    else:
        return '{"vit_status":2,"vit_message":"201"}'
    try:
        res = tunein_request(url)
        # requests.packages.urllib3.disable_warnings()
        # res = requests.get(url=url, timeout=15, verify=False)
    except:
        return json.dumps({"vit_status": 4, "vit_message": "444"})
    if res.status_code == 200:
        info_dic = json.loads(res.text)
        
        play_url = info_dic.get('Items')[-1].get('Actions', {}).get('Play', {}).get("PlayUrl", '')
        nextguideid = info_dic.get('Items')[-1].get('Actions', {}).get('Play', {}).get("NextGuideId", '')  #
        # 方案：采用添加到播放队列的下一首播放
        if nextguideid:
            next_parameter_dic = {'guideid': nextguideid}
            tunein_play_program(next_parameter_dic, write_type='a+')

        if not play_url:
            return json.dumps({"vit_status": 4, "vit_message": "445"})
        else:
            tunein_play_id=json.dumps({"GuideId": info_dic.get('Items')[-1].get('Actions', {}).get('Play', {}).get("GuideId", ''), "PreferredGuideId": info_dic.get('Items')[-1].get('Actions', {}).get('Play', {}).get("PreferredGuideId", '')})
            with open("/mnt/mpd/tunein.json", 'w')as f:
                f.write(tunein_play_id)
                
            play_str = play_url.split('?')[0]
            if play_str.endswith('.m3u'):
                playurl = requests.get(play_url, timeout=15).text
                return playurl
            elif play_str.endswith('.pls'):
                info_text = requests.get(play_url, timeout=15).text
                playurl = ''.join(re.findall('File1=(.+)\n', info_text)).replace('\r', '')
                return playurl
            # elif play_str.endswith('.mp3'):
            #     info_text=requests.get(play_url).text
            #     print(info_text)

            else:
                play_url=play_url.replace('\r', '')
                result = list(urlparse(play_url))
                result[1] = result[1].lower()
                play_url=urlunparse(result)
                return play_url


    else:
        return json.dumps({"vit_status": 4, "vit_message": res.status_code})


def tunein_play_program(parameter_dic, write_type='w+'):
    guideid = parameter_dic.get('guideid')
    if not guideid:
        return json.dumps({"vit_status": 2, "vit_message": "201"})

    station_info = json.loads(tunein_profiles_endpoint(parameter_dic))  # 获取电台或者博客节目的信息
    # isLive=station_info.get('Item',{}).get('Actions',{}).get('Play',{}).get('IsLive')
    can_play = station_info.get('Item', {}).get('Actions', {}).get('Play', {}).get('CanPlay')

    subscriptionrequired = station_info.get('Item', {}).get('Actions', {}).get('Play', {}).get('SubscriptionRequired')

    # 这个值tunein那边会判断用户需不需要订阅 如：一个收费电台 如果是订阅用户 subscriptionrequired=False代表用户可以播放  如果是未订阅用户返回True代表用户需要订阅才能播放。
    # if can_play!=True or isLive ==False:
    if can_play != True and not can_play:
        return json.dumps({"vit_status": 4, "vit_message": "The radio station is not supported at the moment"})
    if subscriptionrequired == True:
        return json.dumps({"vit_status": 4, 'vit_message': 'You need subscription required to play'})

    play_guideid = station_info.get('Item', {}).get('Actions', {}).get('Play', {}).get('GuideId')

    station_image = station_info.get('Item', {}).get('Image')
    station_name = station_info.get('Item', {}).get('Title')
    description = station_info.get('Item', {}).get('Description')
    if description:
        description = description.replace('\n', ' ')  # 描述中不能出现换行符
    if station_name:
        station_name = station_name.replace('\n', ' ')
    duration = station_info.get('Item', {}).get('Actions').get('Play', {}).get("Duration", "None")

    play_url = vit_prefix + play_guideid
    info = 'song_begin: {}\n'.format(play_url)
    info += f'Cover: {station_image}\n'
    info += f'Title: {station_name}\n'
    info += f'Description: {description}\n'
    info += f'Duration: {duration}\n'
    info += 'song_end\n'

    info_dir = os.path.dirname(app_station_info)
    if not os.path.exists(info_dir):
        os.makedirs(info_dir)

    with open(app_station_info, write_type, encoding='utf8')as f:
        f.write(info)

    if write_type == 'w+':
        os.system(
            'mpc clear > /dev/null 2>&1 && mpc add {}  > /dev/null 2>&1 && mpc play > /dev/null 2>&1'.format(play_url))
        return '{"vit_status":0,"vit_message":"' + play_url + '"}'
    else:
        os.system('mpc insert {}  > /dev/null 2>&1'.format(play_url))
        return '{"vit_status":0,"vit_message":"' + play_url + '"}'

def tunein_report_stream(parameter_dic):
    base_url = 'https://report.core-api.tunein.com/report/stream'
    latlon = parameter_dic.get('latlon')
    guideid = parameter_dic.get('guideid')
    listen_id = parameter_dic.get('listen_id')
    stream_id = parameter_dic.get('stream_id')
    if not guideid:
        return json.dumps({"vit_status": 2, "vit_message": "201"})
    if not stream_id:
        return json.dumps({"vit_status": 2, "vit_message": "202"})
    if latlon:
        latitude = latlon.split(',')[0]
        longitude = latlon.split(',')[1]
    else:
        latitude = None
        longitude = None
    data = {
        "client_id": {
            "partner_id": partnerId,
            "serial": serial,
            "version": "1.0"
        },
        "location": {
            "latitude": listen_id,
            "longitude": longitude
        },
        "report_info": {
            "guide_id": guideid,
            "listen_id": int(listen_id)
        },
        "stream_id": 101695550,
        "tune_result": "SUCCESS"
    }
    print(data)
#    url=structure_url(base_url,parameter_dic)

    headers = {"x-API-key": "NUdLVXNqQVU6WllsNkNZTkxtT1E2"}

    requests.packages.urllib3.disable_warnings()
    try:
        res = requests.post(url=base_url, headers=headers, json=data, verify=False, timeout=15)

    except requests.exceptions.ReadTimeout:
        url=base_url.replace('https','http',max=1)
        res = requests.post(url=base_url, headers=headers, json=data, verify=False, timeout=15)
    
#    res = tunein_request(base_url)
    info = res.text
    print(info, res.status_code)
    return info

def tunein_report_listen(parameter_dic):
    base_url = 'https://report.core-api.tunein.com/report/listen'
    latlon = parameter_dic.get('latlon')
    guideid = parameter_dic.get('guideid')
    listen_id = parameter_dic.get('listen_id')
    if not guideid:
        return json.dumps({"vit_status": 2, "vit_message": "201"})
    if latlon:
        latitude = latlon.split(',')[0]
        longitude = latlon.split(',')[1]
    else:
        latitude = None
        longitude = None
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
        "duration": 20,
        "report_info": {
            "guide_id": guideid,
            "listen_id": int(listen_id)
        },
        "trigger": "STOP"
    }
    print(data)
#    url=structure_url(base_url,parameter_dic)

    headers = {"x-API-key": "NUdLVXNqQVU6WllsNkNZTkxtT1E2"}

    requests.packages.urllib3.disable_warnings()
    try:
        res = requests.post(url=base_url, headers=headers, json=data, verify=False, timeout=15)

    except requests.exceptions.ReadTimeout:
        url=base_url.replace('https','http',max=1)
        res = requests.post(url=base_url, headers=headers, json=data, verify=False, timeout=15)
    
#    res = tunein_request(base_url)
    info = res.text
    print(info, res.status_code)
    return info
    
def main():
    try:
        tunein_parameter = sys.argv[2]
    except:
        tunein_parameter = ''
    try:
        tunein_manage = sys.argv[1]
    except:
        tunein_manage = ''

    if tunein_parameter:
        try:
            parameter_dic = tunein_parameter_dic(parameter=tunein_parameter)
            if 'tunein_manage' in parameter_dic:
                del parameter_dic['tunein_manage']
        except:
            parameter_dic = {}
    else:
        parameter_dic = {}

    if tunein_manage == 'get_token':
        print(get_token(parameter_dic=parameter_dic))
        sys.exit(0)
    elif tunein_manage == 'refresh_token':
        print(tunein_refresh_token())
        sys.exit(0)
    elif tunein_manage == 'maybe_login':
        data = maybe_login()
        print(data)
        sys.exit(0)
    elif tunein_manage == 'logout':
        data = logout()
        print(data)
        sys.exit(0)

    global headers, username
    headers, username = get_headers_and_username(parameter_dic=parameter_dic)

    if 'latlon' in parameter_dic:
        del parameter_dic['latlon']

    if tunein_manage != 'track_url':
        latlon = parameter_dic.get('latlon')
        if latlon:
            latitude = latlon.split(',')[0]
            longitude = latlon.split(',')[1]
        else:
            latitude = None
            longitude = None
        tunein_latlon=json.dumps({"latitude": latitude, "longitude": longitude})
        with open("/mnt/mpd/tunein_latlon.json", 'w')as f:
            f.write(tunein_latlon)

    if tunein_manage == "seach":
        seach_info = tunein_seach(parameter_dic=parameter_dic)
        print(seach_info)
    elif tunein_manage == 'home':
        home_info = tunein_home(parameter_dic=parameter_dic)
        print(home_info)
    elif tunein_manage == "local_radio":
        beword_info = tunein_local_radio(parameter_dic=parameter_dic)
        print(beword_info)
    elif tunein_manage == 'recents':
        recents_info = tunein_recents(parameter_dic=parameter_dic)
        print(recents_info)
    elif tunein_manage == 'trending':
        trending_info = tunein_trending(parameter_dic=parameter_dic)
        print(trending_info)
    elif tunein_manage == 'music':
        music_info = tunein_music(parameter_dic=parameter_dic)
        print(music_info)
    elif tunein_manage == 'sport':
        sport_info = tunein_sport(parameter_dic=parameter_dic)
        print(sport_info)
    elif tunein_manage == 'talk_and_news':
        talk_info = tunein_talk_and_new(parameter_dic=parameter_dic)
        print(talk_info)
    elif tunein_manage == 'podcasts':
        podcasts_info = tunein_podcasts(parameter_dic=parameter_dic)
        print(podcasts_info)

    elif tunein_manage == 'by_location':
        by_location_info = tunein_by_location(parameter_dic=parameter_dic)
        print(by_location_info)

    elif tunein_manage == 'by_language':
        by_language_info = tunein_by_languages(parameter_dic=parameter_dic)
        print(by_language_info)
    elif tunein_manage == 'user_favorite':
        user_favorite_info = get_user_favorite(parameter_dic=parameter_dic)
        print(user_favorite_info)
    elif tunein_manage == 'add_or_delete_favorite':
        action_favorite_info = add_or_delete_favorite(parameter_dic=parameter_dic)
        print(action_favorite_info)

    elif tunein_manage == "media":
        media_info = tunein_media(parameter_dic=parameter_dic)
        print(media_info)
    elif tunein_manage == "profiles_endpoint":
        profiles_info = tunein_profiles_endpoint(parameter_dic=parameter_dic)
        print(profiles_info)

    elif tunein_manage == 'get_user_info':
        user_info = tunein_get_user_info(parameter_dic=parameter_dic)
        print(user_info)
    elif tunein_manage == 'beword':
        beword_info = beword(parameter_dic=parameter_dic)
        print(beword_info)
    elif tunein_manage == 'now_playing':
        now_playing_info = tunein_now_playing(parameter_dic=parameter_dic)
        print(now_playing_info)
    elif tunein_manage == 'common':
        info = tunein_common(parameter_dic=parameter_dic)
        print(info)
    elif tunein_manage == 'track_url':
        info = get_play_url(parameter=tunein_parameter)
        print(info)
    elif tunein_manage == 'play_program':
        info = tunein_play_program(parameter_dic=parameter_dic)
        print(info)
    elif tunein_manage == 'report_stream':
        info = tunein_report_stream(parameter_dic=parameter_dic)
        print(info)
    else:
        print('{"vit_status":98,"vit_message":"987"}')


if __name__ == '__main__':
    main()

#    get_headers_and_username(parameter_dic={})

#    global headers, username
#    headers, username = get_headers_and_username(parameter_dic={})
#    print(tunein_refresh_token())
#    global headers, username
#    headers, username = get_headers_and_username(parameter_dic={})
    # code='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE2NDI4MzIzOTMsImlhdCI6MTYzOTYzNTU5Mywic3ViIjoiMjUzMTA5NTEyIiwidXNlcm5hbWUiOiJ0aHVuZGVyZGF0YXAiLCJkYXRhIjoiTXwyNTkzMiIsInNjb3BlcyI6IiIsInZlcnNpb24iOjB9.s6nXp4jfTGWtQb_14WUjJPu1lMic_ZcqVhrhJ7HDJCU'
    # print(get_username(code))


    # global username
#    parameter='guideid=t128529588&latlon=22.324386,114.031040&stream_id=101695550&listen_id=1654508775'
#    parameter_dic = tunein_parameter_dic(parameter)
#    tunein_report_stream(parameter_dic)

#    parameter='guideid=t128529588&latlon=22.324386,114.031040&listen_id=1654508775'
#    parameter_dic = tunein_parameter_dic(parameter)
#    tunein_report_listen(parameter_dic)





    # print(get_play_url('track_id=t168342479'))
    # parameter="guideid=s14488"
    # parameter='guideid=s7641'
    # parameter="guideid=t167020955"
    # parameter='guideid=s24940'
    # parameter='guideid=s258420'
    # parameter_dic=tunein_parameter_dic(parameter)
    # tunein_play_program(parameter_dic=parameter_dic)
    # playurl=get_play_url(parameter_dic)
    # print(playurl)
    # os.system('mpc clear > /dev/null 2>&1 && mpc add {}  > /dev/null 2>&1 && mpc play 1 > /dev/null 2>&1'.format(playurl))
    # beword()


    # print(tunein_listen())
    # print(json.dumps(tunein_get_user_info(parameter='username=thunderdatap')))
    # print(json.dumps(beword(parameter='username=thunderdatap')))
    # print(json.dumps(tunein_home(parameter='username=thunderdatap')))
    # print(tunein_now_playing(parameter='guideid=p138450'))
    # print(refresh_token())
    # parameter="code=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE2NDIyMTc1MTUsImlhdCI6MTYzOTAyMDcxNSwic3ViIjoiMjUzMTA5NTEyIiwidXNlcm5hbWUiOiJ0aHVuZGVyZGF0YXAiLCJkYXRhIjoiTXwyNTkzMiIsInNjb3BlcyI6IiIsInZlcnNpb24iOjB9.MsccueEPGObXjjSR6B3FJmutj6J3jqp1AHgkqbqrcw4"


    # parameter_dic=tunein_parameter_dic(parameter)
    # get_token(parameter_dic)

    # print(tunein_talk())
    # print(tunein_music())
    # print(tunein_sport())
    # print(tunein_by_location())
    # parameter_dic=tunein_parameter_dic(parameter='guideid=s258420&username=thunderdatap')
    # parameter_dic=tunein_parameter_dic(parameter='guideid=t83373281&username=thunderdatap')
    # print(json.dumps(tunein_media(parameter_dic=parameter_dic)))
    # print(json.dumps(tunein_profiles_endpoint(parameter='guideid=p1238422')))
    # print(json.dumps(tunein_profiles_endpoint(parameter='guideid=s24940')))
    # print(json.dumps(tunein_seach(parameter='query=love')))
    # print(tunein_get_user_info(username='thunderdatap'))
    # print(json.dumps(tunein_home(parameter='username=thunderdatap')))
    # print(json.dumps(get_user_favorite(parameter='username=thunderdatap')))
    # print(json.dumps(add_or_delete_favorite2(username='thunderdatap',guideid='s249995',action='delete')))
    # print(add_or_delete_favorite2(username='thunderdatap',guideid='',action='add'))



