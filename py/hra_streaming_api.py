# *encoding=utf-8
import requests
import json
import os
import urllib.parse
import sys
import logging

logging.captureWarnings(True)
base_url = "https://streaming.highresaudio.com:8182/vault3"
info_path = "/mnt/settings/hra/login_info"
user_info = {}
auto_login = '0'  # 值为1会自动登录一次


# ----------------------------------------7. USER HANDLING--------------------------------------------------

# 登录
def user_login(parameter):
    if not parameter:
        return '{"vit_status":1,"vit_message":"101"}'
    dir_params = {}
    try:
        parameter_list = parameter.split('&')
        for parameter in parameter_list:
            if -1 == parameter.find('='):
                continue
            key = urllib.parse.unquote(parameter.split('=', 1)[0])
            value = urllib.parse.unquote(parameter.split('=', 1)[1])
            dir_params[key] = value
    except Exception:
        pass
    username = dir_params.get('username', '')
    if not username:
        return '{"vit_status":1,"vit_message":"102"}'
    password_aes = dir_params.get('password', '')
    if not password_aes:
        return '{"vit_status":1,"vit_message":"103"}'
    return hra_login(username, password_aes)


# 重新登录
def user_re_login():
    if not os.path.exists(info_path):
        return '{"vit_status":1,"vit_message":"101"}'
    try:
        with open(info_path) as f:
            user = json.load(f)
        username = user.get('username')
        password_aes = user.get('password')
    except Exception:
        return '{"vit_status":1,"vit_message":"104"}'
    if not username:
        return '{"vit_status":1,"vit_message":"102"}'
    if not password_aes:
        return '{"vit_status": 1, "vit_message": "103"}'
    return hra_login(username, password_aes)


# 调用hra的登录功能
def hra_login(username, password_aes):
    password = "".join(os.popen('thunder_aes_cbc128 {}'.format(password_aes)).readlines()).strip()
    if not password:
        return '{"vit_status": 1, "vit_message": "104"}'

    endpoint = '/user/login'
    data_query = {'username': username, 'password': password}
    try:
        succeed, user_data = hra_requests_post(base_url + endpoint, data_query)
        if not succeed:
            return '{"vit_status":4,"vit_message":"' + str(user_data) + '"}'
        try:
            response_json = json.loads(user_data)
        except json.decoder.JSONDecodeError:
            return {"vit_status": 4, "vit_message": "555"}

        response_status = response_json.get("response_status")
        if response_status == "OK":
            user_info_save(username, password_aes, user_data)
            return json.dumps({"vit_status": 0, "vit_message": "", "username": username, "subscription": True})

        error_code = response_json.get("error_code")
        if error_code == "NO_SUBSCRIPTION":  # 登陆成功 账号未订阅
            user_info_save(username, password_aes, user_data)
            return json.dumps({"vit_status": 0, "vit_message": "", "username": username, "subscription": False})

        # 账号或者密码错误或者其他原因导致登陆错误
        return json.dumps({"vit_status": 1, "vit_message": "109"})
    except Exception:
        return json.dumps({"vit_status": 4, "vit_message": "444"})


# 登录成功后存储用户名、密码、用户信息
def user_info_save(username, password_aes, user_data):
    info_dir = os.path.dirname(info_path)
    if not os.path.exists(info_dir):
        os.makedirs(info_dir)
    with open(info_path, 'w+', encoding='utf8') as f:
        data_save = {'username': username, 'password': password_aes, 'userData': user_data}
        global user_info
        user_info = data_save
        f.write(json.dumps(data_save))


# 只存储用户名、密码
def user_info_save_not_user_data(username, password_aes):
    info_dir = os.path.dirname(info_path)
    if not os.path.exists(info_dir):
        os.makedirs(info_dir)
    with open(info_path, 'w+', encoding='utf8') as f:
        data_save = {'username': username, 'password': password_aes}
        global user_info
        user_info = data_save
        f.write(json.dumps(data_save))


# 登出
def user_logout():
    try:
        if os.path.exists(info_path):
            os.remove(info_path)
        global user_info
        user_info = {}
        try:
            os.system('mpc playlistdel http://online.silentangel.audio/hra > /dev/null 2>&1')
            info = ''
            skip_hra = False
            import hra_play as play
            with open(play.app_song_info, encoding='utf8') as f:
                for line in f:
                    if line.startswith("song_begin: " + play.vit_prefix):
                        skip_hra = True
                    if skip_hra:
                        if line.startswith("song_end"):
                            skip_hra = False
                        continue
                    else:
                        info += line
            with open(play.app_song_info, 'w+', encoding='utf8') as f:
                f.write(info)
        except Exception:
            pass
        hra_requests(base_url + '/user/logout', None)
    except Exception:
        return '{"vit_status":1,"vit_message":"101"}'
    return '{"vit_status":0,"vit_message":""}'


# 查询用户信息和登录状态
def get_user_info():
    try:
        for k in range(2 if '1' == auto_login else 1):
            user_data = user_info.get('userData')
            url = base_url + "/user/ListSingleUserPlaylist?playlist_id=0&userData=" + user_data
            succeed, response_info = hra_requests(url, None)
            if not succeed:
                return response_info
            status = response_info.get('response_status', False)
            message = response_info.get('error_code', False)

            username = user_info.get('username')
            if status == 'NOK':
                if message == 'NO SUBSCRIPTION':
                    return json.dumps(
                        {"vit_status": 0, "vit_message": "102", "username": username, "subscription": False})
                elif message == "NOT LOGGED IN":
                    password = user_info.get('password')
                    if 0 == k and '1' == auto_login:  # 自动登录一次
                        re_info = hra_auto_re_login()
                        if not isinstance(re_info, str):
                            user_info_save_not_user_data(username, password)
                            return json.dumps({"vit_status": 1, "vit_message": str(re_info), "username": username})
                        continue
                    user_info_save_not_user_data(username, password)
                    return json.dumps({"vit_status": 1, "vit_message": "103", "username": username})
                elif message == "NO DATA FOUND":
                    return json.dumps({"vit_status": 0, "vit_message": "", "username": username, "subscription": True})
                else:
                    return json.dumps({"vit_status": 1, "vit_message": "105", "username": username})
            elif not status:  # status == False
                return json.dumps({"vit_status": 4, "vit_message": "666", "username": username})
            else:
                return json.dumps({"vit_status": 0, "vit_message": "", "username": username, "subscription": True})
    except Exception:
        return '{"vit_status":4,"vit_message":"444"}'


def hra_params_dic(parameter):
    if not os.path.exists(info_path):
        return '{"vit_status":1,"vit_message":"101"}'
    try:
        with open(info_path) as f:
            global user_info
            user_info = json.load(f)
            global auto_login
            auto_login = '1'
            if not user_info.get('userData'):
                return json.dumps({"vit_status": 1, "vit_message": "103", "username": user_info.get('username')})
    except Exception:
        return '{"vit_status":1,"vit_message":"104"}'

    params_dic = {}
    try:
        parameter_list = parameter.split('&')
        for parameter in parameter_list:
            if -1 == parameter.find('='):
                continue
            params = parameter.split('=', 1)
            key = urllib.parse.unquote(params[0])
            value = urllib.parse.unquote(params[1])
            params_dic[key] = value
        if not params_dic.get('lang'):
            params_dic['lang'] = 'en'
        return params_dic
    except Exception:
        return params_dic


def hra_requests_post(url, data_query):
    try:
        response = None
        for i in range(10):
            try:
                response = requests.post(url=url, data=data_query, verify=False, timeout=58)
                break
            except requests.exceptions.SSLError:
                return False, 579
            except requests.exceptions.ConnectTimeout:  # 连接超时
                return False, 578
            except requests.exceptions.ConnectionError:
                if 9 == i:
                    return False, 577
                else:
                    continue
        if response is None:
            return False, 576
        if response.status_code != 200:
            return False, response.status_code
        return True, response.text
    except Exception:  # 其他错误
        return 444


def hra_requests(url, params_dic):
    try:
        response = None
        for i in range(10):
            try:
                response = requests.get(url, params=params_dic, verify=False, timeout=58)
                break
            except requests.exceptions.SSLError:
                return False, '{"vit_status":4,"vit_message":"579"}'
            except requests.exceptions.ConnectTimeout:  # 连接超时
                return False, '{"vit_status":4,"vit_message":"578"}'
            except requests.exceptions.ConnectionError:
                if 9 == i:
                    return False, '{"vit_status":4,"vit_message":"577"}'
                else:
                    continue
        if response is None:
            return False, '{"vit_status":4,"vit_message":"576"}'
        if response.status_code != 200:
            return False, '{"vit_status":4,"vit_message":"' + str(response.status_code) + '"}'  # 请求错误
        if response.text[0] == '{':
            response_json = json.loads(response.text)  # print(response.text)
        else:
            str_new = ''
            is_json = False
            for line in response.text.splitlines():
                if line[0] == '{':
                    is_json = True
                if is_json:
                    str_new += line
            response_json = json.loads(str_new)  # print(response.text)
    except Exception:  # 其他错误
        return False, '{"vit_status":4,"vit_message":"443"}'

    return True, response_json


def hra_data_str(api_endpoint, params_dic=None):
    try:
        if params_dic is None:
            params_dic = {}
        for k in range(2 if '1' == auto_login else 1):
            params_dic['userData'] = user_info.get('userData')
            succeed, response_json = hra_requests(base_url + api_endpoint, params_dic)
            if not succeed:
                return response_json

            status = response_json.get('status')
            response_status = response_json.get('response_status')
            if not status and not response_status:  # 没有需要的信息
                response_json['vit_status'] = 4
                response_json['vit_message'] = '445'
                return json.dumps(response_json)

            if not status:
                if response_status == 'NOK':
                    error_code = response_json.get('error_code')
                    if error_code:
                        status = error_code
                    else:
                        status = response_status
            if status == 'NOT LOGGED IN':
                username = user_info.get('username')
                password = user_info.get('password')
                if 0 == k and '1' == auto_login:  # 自动登录一次
                    re_info = hra_auto_re_login()
                    if not isinstance(re_info, str):
                        user_info_save_not_user_data(username, password)
                        return json.dumps({"vit_status": 1, "vit_message": str(re_info), "username": username})
                    continue
                user_info_save_not_user_data(username, password)
                return json.dumps({"vit_status": 1, "vit_message": "103", "username": username})
            elif status == "NO SUBSCRIPTION":
                username = user_info.get('username')
                return json.dumps({"vit_status": 1, "vit_message": "102", "username": username})
            elif status == "NO DATA FOUND":
                response_json['vit_status'] = 0
                response_json['vit_message'] = '446'
            elif status == 'NOK':
                response_json['vit_status'] = 0
                response_json['vit_message'] = '447'
            else:
                response_json['vit_status'] = 0
                response_json['vit_message'] = ''
            return json.dumps(response_json)
    except Exception:  # 其他错误
        return '{"vit_status":4,"vit_message":"444"}'


def hra_auto_re_login():
    username = user_info.get('username')
    if not username:
        return 1032

    password_aes = user_info.get('password')
    if not password_aes:
        return 1033

    password = "".join(os.popen('thunder_aes_cbc128 {}'.format(password_aes)).readlines()).strip()
    if not password:
        return 1034

    try:
        endpoint = '/user/login'
        data_query = {'username': username, 'password': password}
        succeed, txt = hra_requests_post(base_url + endpoint, data_query)
        if not succeed:
            return 1035
        user_info_save(username, password_aes, txt)
        try:
            json.loads(txt).get("response_status")
        except json.decoder.JSONDecodeError:
            return 1036
        return txt
    except Exception:
        return 1037


# --------------------------------------------1.CATALOG-----------------------------------------
# 1.1
# :return: 音乐的类别信息
def available_categories(params_dic):
    endpoint = '/vault/categories/ListAllCategories/'
    response_info = json.loads(hra_data_str(endpoint, params_dic))
    try:
        results = response_info['data']['results']
        new_results = []
        for key, value in results.items():
            value['vit_index'] = key
            new_results.append(value)
        response_info['data']['results'] = new_results
        return json.dumps(response_info)
    except Exception:
        return response_info


# 1.2
def available_genre(params_dic):
    endpoint = "/vault/categories/ListAllGenre/"
    return hra_data_str(endpoint, params_dic)


# 1.3
# category=/HIGHRES%20AUDIO/Musicstore/Genre/Soundtrack/Music
# 改成
# category=/HIGHRES%20AUDIO/Musicstore/&genre=Soundtrack&subgenre=Music
def list_categoriecontent(params_dic):
    category = params_dic.get('category')
    if not category:
        return '{"vit_status":2,"vit_message":"201"}'
    if '&' in category and 'Genre/' in category:
        params = category.split('Genre/', 1)
        params_dic['category'] = params[0]
        params_1 = params[1]
        if '/' in params_1:
            params_1s = params_1.split('/', 1)
            params_dic['genre'] = params_1s[0]
            params_dic['subgenre'] = params_1s[1]
        else:
            params_dic['genre'] = params_1
    endpoint = '/vault/categories/ListCategorieContent/'
    return default_offset_and_limit(endpoint, params_dic)


def default_sort(endpoint, params_dic):
    if not params_dic.get('sort'):
        params_dic['sort'] = '+ added'
    return default_offset_and_limit(endpoint, params_dic)


def default_offset_and_limit(endpoint, params_dic):
    if not params_dic.get('offset'):
        params_dic['offset'] = '0'
    if not params_dic.get('limit'):
        params_dic['limit'] = '30'
    return hra_data_str(endpoint, params_dic)


# ----------------------------------------2. ALBUMDETAILS---------------------------------------------------
# 2.1
def album_details(params_dic):
    if not params_dic.get('album_id'):
        return '{"vit_status":2,"vit_message":"201"}'
    endpoint = "/vault/album/"
    return hra_data_str(endpoint, params_dic)


# ---------------------------------------------------3. SINGLE TRACK OF ALBUM-------------------------------------------

def single_track_or_album(params_dic):
    if not params_dic.get('track_id'):
        return '{"vit_status":2,"vit_message":"201"}'
    endpoint = "/vault/track"
    return hra_data_str(endpoint, params_dic)


# ---------------------------------------------------4. ARTISTLIST------------------------------------------
def artists_list(params_dic):
    endpoint = "/vault/ListAllArtists/"
    return hra_data_str(endpoint, params_dic)


# ---------------------------------------------------5. EDITORIAL PLAYLISTS---------------------------------------------
def list_of_available_moods(params_dic):
    endpoint = "/vault/getEditorPlaylistsMoods/"
    return hra_data_str(endpoint, params_dic)


def list_of_available_genre(params_dic):
    endpoint = "/vault/getEditorPlaylistsGenres/"
    return hra_data_str(endpoint, params_dic)


def list_of_available_themes(params_dic):
    endpoint = '/vault/getEditorPlaylistsThemes/'
    return hra_data_str(endpoint, params_dic)


def list_all_available_editorial_playlists(params_dic):
    endpoint = "/vault/editorPlaylists/"
    return default_offset_and_limit(endpoint, params_dic)


def details_of_an_editorial_playlist(params_dic):
    if not params_dic.get('id'):
        return '{"vit_status":2,"vit_message":"201"}'
    endpoint = '/vault/getSingleEditorPlaylists/'
    return hra_data_str(endpoint, params_dic)


# ---------------------------------------------------6. SEARCH----------------------------------------------
def quicksearch(params_dic):
    search = params_dic.get('search')
    if not search:
        return '{"vit_status":2,"vit_message":"201"}'
    if len(search) < 3:
        return '{"vit_status":2,"vit_message":"209"}'
    endpoint = '/vault/search/quickSearch'
    return hra_data_str(endpoint, params_dic)


def search_in_categories(params_dic):
    if not params_dic.get('category'):
        return '{"vit_status":2,"vit_message":"201"}'
    search = params_dic.get('search')
    if not search:
        return '{"vit_status":2,"vit_message":"202"}'
    if len(search) < 3:
        return '{"vit_status":2,"vit_message":"209"}'
    endpoint = '/vault/SearchInCategory/'
    return hra_data_str(endpoint, params_dic)


def search_in_compilation(params_dic):
    search = params_dic.get('search')
    if not search:
        return '{"vit_status":2,"vit_message":"201"}'
    if len(search) < 3:
        return '{"vit_status":2,"vit_message":"209"}'
    endpoint = '/vault/SearchInCompilation/'
    return hra_data_str(endpoint, params_dic)


def Advanced_Search(params_dic):
    search = params_dic.get('search')
    if not search:
        return '{"vit_status":2,"vit_message":"201"}'
    if len(search) < 3:
        return '{"vit_status":2,"vit_message":"209"}'
    endpoint = '/vault/AdvancedSearch/'
    return default_offset_and_limit(endpoint, params_dic)


# album_id='424c798f-02bc-4703-80d0-1567dd3858c0'
# return response.text
# ---------------------------------------------------8. USER-PLAYLIST HANDLING------------------------------------------
def list_all_user_playlists(params_dic):
    endpoint = '/user/ListAllUserPlaylists'
    return hra_data_str(endpoint, params_dic)


def get_single_user_playlist(params_dic):
    if not params_dic.get('playlist_id'):
        return '{"vit_status":2,"vit_message":"201"}'
    endpoint = '/user/ListSingleUserPlaylist'
    return hra_data_str(endpoint, params_dic)


def create_user_playlist(params_dic):
    if not params_dic.get('playlist_title'):
        return '{"vit_status":2,"vit_message":"201"}'
    endpoint = '/user/CreateUserPlaylist'
    return hra_data_str(endpoint, params_dic)


def delete_userplaylist(params_dic):
    if not params_dic.get('playlist_id'):
        return '{"vit_status":2,"vit_message":"201"}'
    endpoint = '/user/DeleteUserPlaylist'
    return hra_data_str(endpoint, params_dic)


def rename_playlist(params_dic):
    if not params_dic.get('playlist_id'):
        return '{"vit_status":2,"vit_message":"201"}'
    if not params_dic.get('playlist_title'):
        return '{"vit_status":2,"vit_message":"202"}'
    endpoint = '/user/RenameUserPlaylist'
    return hra_data_str(endpoint, params_dic)


def add_single_track(params_dic):
    if not params_dic.get('playlist_id'):
        return '{"vit_status":2,"vit_message":"201"}'
    if not params_dic.get('id'):
        return '{"vit_status":2,"vit_message":"202"}'
    endpoint = '/user/AddTitleToUserPlaylist'
    return hra_data_str(endpoint, params_dic)


def add_multiple_tracks(params_dic):
    if not params_dic.get('playlist_id'):
        return '{"vit_status":2,"vit_message":"201"}'
    if not params_dic.get('id'):
        return '{"vit_status":2,"vit_message":"202"}'
    endpoint = '/user/AddMultipleTitleToUserPlaylist'
    return hra_data_str(endpoint, params_dic)


def delete_single_track(params_dic):
    if not params_dic.get('playlist_id'):
        return '{"vit_status":2,"vit_message":"201"}'
    if not params_dic.get('id'):
        return '{"vit_status":2,"vit_message":"202"}'
    # endpoint = '/vault/DeleteTitleFromUserPlaylist'
    endpoint = '/user/DeleteTitleFromUserPlaylist'
    return hra_data_str(endpoint, params_dic)


def delete_multiple_tracks(params_dic):
    if not params_dic.get('playlist_id'):
        return '{"vit_status":2,"vit_message":"201"}'
    if not params_dic.get('id'):
        return '{"vit_status":2,"vit_message":"202"}'
    # endpoint = '/vault/DeleteMultipleTitleFromUserPlaylist'
    endpoint = '/user/DeleteMultipleTitleFromUserPlaylist'
    return hra_data_str(endpoint, params_dic)


# ----------------------------------------9. MY ALBUM HANDLING----------------------------------------------
# 9.1
def my_album_list(params_dic):
    endpoint = '/user/list/MyAlbum/'
    return default_sort(endpoint, params_dic)


def add_album_to_my_album_list(params_dic):
    if not params_dic.get('id'):
        return '{"vit_status":2,"vit_message":"201"}'
    endpoint = '/user/list/MyAlbum/add/'
    return hra_data_str(endpoint, params_dic)


def delete_album_from_my_album_list(params_dic):
    if not params_dic.get('id'):
        return '{"vit_status":2,"vit_message":"201"}'
    endpoint = '/user/list/MyAlbum/delete/'
    return hra_data_str(endpoint, params_dic)


# -----------------------------------------------10. “MY TRACKS” HANDLING-----------------------------------------------

def my_track_list(params_dic):
    endpoint = '/user/list/MyTracks/'
    return default_sort(endpoint, params_dic)


def add_single_track_to_my_track_list(params_dic):
    if not params_dic.get('id'):
        return '{"vit_status":2,"vit_message":"201"}'
    endpoint = '/user/list/MyTracks/add/'
    return hra_data_str(endpoint, params_dic)


def add_multiple_tracks_to_my_track_list(params_dic):
    if not params_dic.get('id'):
        return '{"vit_status":2,"vit_message":"201"}'
    endpoint = '/user/list/MyTracks/add/ Multiple/'
    return hra_data_str(endpoint, params_dic)


def delete_single_track_from_my_track_list(params_dic):
    if not params_dic.get('id'):
        return '{"vit_status":2,"vit_message":"201"}'
    endpoint = '/user/list/MyTracks/delete/'
    return hra_data_str(endpoint, params_dic)


def delete_multiple_tracks_from_my_track_list(params_dic):
    if not params_dic.get('id'):
        return '{"vit_status":2,"vit_message":"201"}'
    endpoint = '/user/list/MyTracks/delete/Multiple/'
    return hra_data_str(endpoint, params_dic)


# ------------------------------------------13. main-------------------------------------------
def main():
    try:
        hra_manage = sys.argv[1]
    except Exception:
        print('{"vit_status":98,"vit_message":"986"}')
        sys.exit(98)
    try:
        hra_params = sys.argv[2]
    except Exception:
        hra_params = ''

    # ----------------------------------------7. USER HANDLING--------------------------------------------------
    if hra_manage == 'user_login':
        print(user_login(hra_params))
        return
    if hra_manage == 'user_logout':
        print(user_logout())
        return
    if hra_manage == 'user_re_login':
        print(user_re_login())
        return

    # 先检查用户信息是否存在，并获取session
    params_dic = hra_params_dic(hra_params)
    if isinstance(params_dic, str):
        print(params_dic)
        return

    if hra_manage == "user_info":
        print(get_user_info())
    # ----------------------------------------1.CATALOG---------------------------------------------
    elif hra_manage == 'categories':
        print(available_categories(params_dic))
    elif hra_manage == 'genres':
        print(available_genre(params_dic))
    elif hra_manage == 'albums':
        print(list_categoriecontent(params_dic))

    # ----------------------------------------2. ALBUMDETAILS---------------------------------------------------
    elif hra_manage == 'album_details':
        print(album_details(params_dic))

    # ----------------------------------------3. SINGLE TRACK OF ALBUM------------------------------------------
    elif hra_manage == 'track_details':
        print(single_track_or_album(params_dic))  # 1.4

    # ----------------------------------------4. ARTISTLIST-----------------------------------------
    elif hra_manage == 'artists':
        print(artists_list(params_dic))

    # ----------------------------------------5. EDITORIAL PLAYLISTS--------------------------------------------
    elif hra_manage == 'playlists_moods':
        print(list_of_available_moods(params_dic))
    elif hra_manage == 'playlists_genre':
        print(list_of_available_genre(params_dic))
    elif hra_manage == 'playlists_themes':
        print(list_of_available_themes(params_dic))
    elif hra_manage == 'playlists':
        print(list_all_available_editorial_playlists(params_dic))
    elif hra_manage == 'playlists_details':
        print(details_of_an_editorial_playlist(params_dic))

        # ----------------------------------------6. SEARCH---------------------------------------------
    elif hra_manage == 'HRA_quicksearch':
        print(quicksearch(params_dic))
    elif hra_manage == 'HRA_search_in_categories':
        print(search_in_categories(params_dic))
    elif hra_manage == 'HRA_search_in_compilation':
        print(search_in_compilation(params_dic))
    elif hra_manage == 'search':
        print(Advanced_Search(params_dic))

    # ----------------------------------------8. USER-PLAYLIST HANDLING-----------------------------------------
    elif hra_manage == 'my_playlist':
        print(list_all_user_playlists(params_dic))
    elif hra_manage == 'my_playlist_details':
        print(get_single_user_playlist(params_dic))
    elif hra_manage == 'my_playlist_create':
        print(create_user_playlist(params_dic))
    elif hra_manage == 'my_playlist_delete':
        print(delete_userplaylist(params_dic))
    elif hra_manage == 'my_playlist_change':
        print(rename_playlist(params_dic))
    elif hra_manage == 'my_playlist_track_add':
        print(add_single_track(params_dic))
    elif hra_manage == 'my_playlist_track_add_list':
        print(add_multiple_tracks(params_dic))
    elif hra_manage == 'my_playlist_track_delete':
        print(delete_single_track(params_dic))
    elif hra_manage == 'my_playlist_track_delete_list':
        print(delete_multiple_tracks(params_dic))

    # -------------------------------------9. MY ALBUM HANDLING-----------------------------------------------
    elif hra_manage == 'my_album':
        print(my_album_list(params_dic))
    elif hra_manage == 'my_album_add':
        print(add_album_to_my_album_list(params_dic))
    elif hra_manage == 'my_album_delete':
        print(delete_album_from_my_album_list(params_dic))

    # -----------------------------------10. “MY TRACKS” HANDLING-----------------------------------------------
    elif hra_manage == 'my_track':
        print(my_track_list(params_dic))
    elif hra_manage == 'my_track_add':
        print(add_single_track_to_my_track_list(params_dic))
    elif hra_manage == 'my_track_add_list':
        print(add_multiple_tracks_to_my_track_list(params_dic))
    elif hra_manage == 'my_track_delete':
        print(delete_single_track_from_my_track_list(params_dic))
    elif hra_manage == 'my_track_delete_list':
        print(delete_multiple_tracks_from_my_track_list(params_dic))
    else:
        print('{"vit_status":98,"vit_message":"987"}')  # 98:987是没有输入正确的功能
        sys.exit(98)


if __name__ == '__main__':
    main()
