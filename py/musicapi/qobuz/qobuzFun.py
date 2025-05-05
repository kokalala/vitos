import base64
import json
import os
import sys
import time
import re
from collections import OrderedDict
from fastapi import HTTPException
import hashlib
import requests
import random
from pathlib import Path
# from mainfun import *
import datetime
from qobuz.qobuzConfig import *
from loguru import logger

appVisitTime = time.time()  # app 请求的时间
global qobuzPlayFlag
qobuzPlayFlag = time.time()  # 播放标记，防止列表刷新后，失效的后台数据插入
global isQobuzLogin


def readFile(path):
    data = {}
    if os.path.exists(path):
        with open(path, mode='r+', encoding='utf8') as f:
            try:
                data = json.loads(f.read())
            except:
                pass
            f.close()
    return data


if readFile(info_path):
    isQobuzLogin = True
else:
    isQobuzLogin = False

cacheQobuzList = []  # 缓存列表

allQobuzOrder = {
    "index": {
        "url": "/featured/index",
        "path": "index/index_genre_ids={genre_ids}",
        'cache': [
            {"genre_ids": None},
        ]
    },
    'all_genres': {
        "url": "/genre/list",
        "path": "index/genre_list",
    },
    "featured_albums": {
        "url": "/featured/albums",
        "path": "index/featured_albums_genres",
        'cache': [
            {"genre_ids": None},  # 发现/新发行

        ]
    },
    "album_getfeatured": {
        "url": "/album/getFeatured",
        "path": "index/album_getfeatured/{type}_genres_ids={genre_ids}_offset={offset}_limit={limit}",
        'cache': [
            {"offset": 0, "limit": 30, "type": "new-releases-full", "genre_ids": None},  # 发现/新发行/全部
            {"offset": 0, "limit": 30, "type": "recent-releases", "genre_ids": None},  # 发现/新发行/流行中
            {"offset": 0, "limit": 30, "type": "press-awards", "genre_ids": None},  # 发现/新发行/媒体好评
            {"offset": 0, "limit": 30, "type": "most-streamed", "genre_ids": None},  # 发现/新发行/热门发形
            {"offset": 0, 'limit': 9, 'type': 'qobuzissims', 'genre_ids': None},  # 发现/Qobuz风格/Qobuz全集
            {"offset": 0, 'limit': 30, 'type': 'qobuzissims', 'genre_ids': None},  # 发现/Qobuz风格/Qobuz全集
            {"offset": 0, 'limit': 9, 'type': 'ideal-discography', 'genre_ids': None},  # 发现/Qobuz风格/理想音乐作品集
            {"offset": 0, 'limit': 30, 'type': 'ideal-discography', 'genre_ids': None},  # 发现/Qobuz风格/理想音乐作品集
        ]
    },
    "album_detail": {
        "url": "/album/get",
        "path": "album/{album_id}",
    },
    "artist_detail": {
        "url": "/artist/get",
        "path": "artist/{artist_id}_offset={offset}&limit={limit}",
    },
    "qobuz_playlists": {
        "url": "/playlist/getFeatured",
        "path": "index/qobuz_playlists/{type}_genres_ids={genre_ids}_offset={offset}_limit={limit}",
        'cache': [
            {'offset': 0, 'limit': 30, 'type': 'editor-picks', 'genre_ids': None},
        ]
    },
    "playlist_detail": {
        "url": "/playlist/get",
        "path": "playlist/{playlist_id}_offset={offset}_limit={limit}",
    },
    "get_user_playlists": {
        "url": "/playlist/getUserPlaylists",
        "path": "index/getUserPlaylists_offset={offset}_limit={limit}",
        'cache': [
            {'offset': 0, 'limit': 30},
        ]
    },
    "get_User_Favorites": {
        "url": "/favorite/getUserFavorites",
        "path": "favorite/getUserFavorites_type={type}_offset={offset}_limit={limit}",
        'cache': [
            {'type': None, 'offset': 0, 'limit': 9},
            {'type': 'albums', 'offset': 0, 'limit': 30, 'user_id': None},
            {'type': 'tracks', 'offset': 0, 'limit': 50, 'user_id': None},
            {'type': 'artists', 'offset': 0, 'limit': 30, 'user_id': None}
        ]
    },
    "favorite_ids": {
        "url": "/favorite/getUserFavoriteIds",
        "path": "favorite/getUserFavoriteIds",
    },
    "track_search": {
        "url": "/track/search",
        "path": "search/track_{query}_offset={offset}_limit={limit}",
    },
    "catalog_search": {
        "url": "/catalog/search",
        "path": "search/catalog_{query}_offset={offset}_limit={limit}",
    },
    "album_search": {
        "url": "/album/search",
        "path": "search/album_{query}_offset={offset}_limit={limit}",
    },
    "artist_search": {
        "url": "/artist/search",
        "path": "search/artist_{query}_offset={offset}_limit={limit}",
    },
    "playlist_search": {
        "url": "/playlist/search",
        "path": "search/playlist_{query}_offset={offset}_limit={limit}",
    },

}


# baseUrl = 'http://qobuz.siems-shop360.com/api.json/0.2'

# def initialize_api():
#     global api
#     api = raw.RawApi("950096963", "")
#     vit_status = api.td_qobuz_maybe_login()
#     return vit_status
def setQobuzLoginStatus(status):
    global isQobuzLogin
    global cacheQobuzList
    if status:
        isQobuzLogin = True
    else:
        isQobuzLogin = False
        cacheQobuzList.clear()


def wiatListAndApp():  # 等待cacheList 和 app没有请求后，才返回
    # while cachelLis or abs(int(time.time() - appVisitTime)) < 20:  # cacheList有队列 和 有点击动作
    while abs(int(time.time() - appVisitTime)) < 20:  # cacheList有队列 和 有点击动作
        time.sleep(1)


def getDirSize(dir):  # 获取文件夹大小
    size = 0
    for root, dirs, files in os.walk(dir):
        size += sum([os.path.getsize(os.path.join(root, name)) for name in files])
    return size


def writeCacheFile(path, jsonData):
    if not Path(os.path.dirname(path)).is_dir():
        os.makedirs(os.path.dirname(path).lower())  # 有同名的文件存在不能创建文件夹，需要改成小写

    if len(os.path.basename(path)) < 255:  # 文件名不能大于255
        with open(path, mode='w+', encoding='utf8') as f:
            f.write(''.join(json.dumps(jsonData)))
            f.close()


def clearCache(platform, day=-1, file="*"):  # 清除缓存,-1为全部，day天前的缓存数据
    if day == -1:
        os.popen(f'find {cacheMainDir}/{platform}/ -type f  -name "{file}" -exec rm -rf {{}} \;')
    else:
        os.popen(f'find {cacheMainDir}/{platform}/ -type f -mtime {day} -name "{file}" -exec rm -rf {{}} \;')


def td_qobuz_api_request(params, uri, login=False, userFlag=False):
    global appVisitTime
    appVisitTime = time.time()
    url = baseUrl + uri
    headers = {
        "User-Agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:67.0) Gecko/20100101 Firefox/67.0"
    }
    if not login:
        # print('os.path.exists(info_path):', os.path.exists(info_path))
        if os.path.exists(info_path):  # 如果文件存在则表示用户登陆过
            try:
                with open(info_path) as f:
                    userInfo = json.load(f)
                    f.close()
            except:
                delCacheFile(info_path)
                return {"vit_status": 1, "vit_message": "101"}
        else:
            clearCache('qobuz')  # 执行删除缓存
            return {"vit_status": 1, "vit_message": "101"}

        headers['X-User-Auth-Token'] = userInfo.get('userData', {}).get('user_auth_token')
        headers['X-App-Id'] = userInfo.get('userData', {}).get('appid')
        if userFlag:
            params['user_id'] = userInfo.get('userData', {}).get('user', {}).get('id')
        # print('url:', url)
        # print('params:', params)
        # print('headers:', headers)
        try:
            session = requests.Session()
            r = session.get(url, params=params, headers=headers)
            # if uri in ["/album/get"]:
            #     #params.update({"offset":0,"limit":1000,"extra":"albumsFromSameArtist,focus"})
            #     r = session.get(url, params=params, headers=headers)
            # else:
            #     r = session.post(url, data=params, headers=headers)

        except:
            # 连接请求失败
            return {"vit_status": 4, "vit_message": "444"}
        resp = json.loads(r.text)
        saveQobuzServerTime(r)  # 保存qobuz服务器时间
        if r.status_code != 200:
            # 如果服务器错误则返回对应的状态码
            return {"vit_status": 4, "vit_message": resp['message']}

        if resp.get('status') == 'error':
            return {"vit_status": 4, "vit_message": resp['message']}  # 返回的是错误的数据
        resp['vit_status'] = 0
        resp['vit_message'] = ''
        if userFlag:
            resp['user_id'] = params.get('user_id')

        return resp
    else:  # 登录请求
        try:
            session = requests.Session()
            r = session.post(url, data=params, headers=headers)
        except:
            # 连接请求失败
            return {"vit_status": 4, "vit_message": "444"}
        resp = json.loads(r.text)
        if r.status_code != 200:
            # 如果服务器错误则返回对应的状态码
            return {"vit_status": 4, "vit_message": resp['message']}
    if resp.get('status') == 'error':
        return {"vit_status": 4, "vit_message": resp['message']}  # 返回的是错误的数据
    resp['vit_status'] = 0
    resp['vit_message'] = ''
    return resp


def saveQobuzServerTime(res):
    """
    保存qobuz 服务器时间 和当前系统时间，用于请求播放url时使用
    """
    try:
        headers = res.headers
        GMT_FORMAT = '%a, %d %b %Y %H:%M:%S GMT'
        serverTime = datetime.datetime.strptime(headers.get('Date'), GMT_FORMAT)
        serverTime = time.mktime(serverTime.timetuple())
        nowTime = time.time()
        dat = {'nowTime': int(nowTime), 'serverTime': int(serverTime) + 8 * 3600}  # 服务器时间+8小时
        writeCacheFile(qobuzServerTime, dat)
    except:
        delCacheFile(qobuzServerTime)  # 服务器时间错误或者写入错误，将删除该文件


# def qobuz_get_url_by_id(params_dic):
#     track_id = params_dic.get('track_id')
#     track_info = api.td_qobuz_track_getFileUrl({'track_id': track_id})
#     if track_info.get('vit_status') == 0:
#         play_url = track_info.get('url')
#         if play_url:
#             return play_url
#         else:
#             return {"vit_status": 4, "vit_message": "441"}  # 没有播放链接
#     else:
#         # vit_message = track_info.get('vit_message')
#         return track_info


def qobuz_next_track(parameter, flag='a+'):
    if not os.path.exists(info_path):
        return {"vit_status": 1, "vit_message": "101"}
    if not parameter:
        return {"vit_status": 2, "vit_message": "201"}
    key_list = ['Artist', 'Album', 'AlbumArtist', 'Title', 'Track', 'Genre', 'Date',
                'Cover', 'CoverPreview', 'Label', 'Composer', 'Time', 'duration', 'Format']
    params = ''
    track_id = parameter.get('track_id')
    model = parameter.get('model', 'insert')
    for key in key_list:
        if key in parameter.keys():
            params += f'{key}: {parameter.get(key)}\n'
    if not track_id:
        return {"vit_status": 2, "vit_message": "202"}
    track_url = vit_prefix + track_id

    info = 'song_begin: {}\n{}song_end\n'.format(track_url, params)
    info_dir = os.path.dirname(app_song_info)
    if not os.path.exists(info_dir):
        os.makedirs(info_dir)
    with open(app_song_info, flag, encoding='utf8') as f:
        f.write(info)
    if flag == 'w+':
        os.system(f'{COMMAND_MPC} clear > /dev/null 2>&1 && {COMMAND_MPC} add {track_url}  > /dev/null 2>&1 && {COMMAND_MPC} play > /dev/null 2>&1')
    else:
        if 'insert' == model:
            os.system(f'{COMMAND_MPC} insert {track_url}  > /dev/null 2>&1')
        elif 'play' == model:
            pass  # 播放由app调用插入mpd和播放
             # os.system(f'{COMMAND_MPC} insert {track_url}  > /dev/null 2>&1')
        else:
            os.system(f'{COMMAND_MPC} add {track_url}  > /dev/null 2>&1')

    return {"vit_status": 0, "vit_message": track_id}


# def qobuz_play_album1(parameter_dic, type):  # parameter 一般包含album_id和track_id 至少包含album_id
#     # parameter_dic = api.td_qobuz_parameter_dic(parameter)
#     # if parameter:
#     #     album_id = parameter_dic.get('album_id')
#     #     track_id = parameter_dic.get('track_id')
#     #
#     # else:
#     #     return parameter
#     global api
#     album_id = parameter_dic.get('album_id')
#     track_id = parameter_dic.get('track_id')
#     # try:
#     album_info = api.td_qobuz_album_get({'album_id': album_id})
#     print(json.dumps(album_info))
#     if album_info.get('vit_status') == 0:
#         tracks = album_info.get('tracks').get('items')
#     else:
#         return album_info
#     # except:
#     # return {"vit_status": 4, "vit_message": "888"}
#     info_public = ''
#
#     dict_album = {'title': 'Album', 'artists': 'Artist', 'genre': 'Genre', 'release_date_original': 'Date', 'label': 'Label', 'composer': 'Composer'}
#     for key in dict_album.keys():
#         if key == 'genre' or key == 'composer' or key == 'performer' or key == 'label':
#             value = album_info.get(key)
#             if value is not None:
#                 value = value.get('name')
#             else:
#                 continue
#         else:
#             value = album_info.get(key)
#
#         if not value:
#             continue
#         if key == 'artists':
#             for artist in value:
#                 name = artist.get('name')
#                 if name is not None:
#                     info_public += f'Artist: {name}\n'
#                 else:
#                     continue
#             continue
#         info_public += '{}: {}\n'.format(dict_album[key], value)
#
#     image_large = album_info.get('image').get('large', '')
#     if image_large:
#         info_public += f'Cover: {image_large}\n'
#
#     image_small = album_info.get('image').get('small', '')
#     if image_small:
#         info_public += f'CoverPreview: {image_small}\n'
#
#     dict_track = {"performer": 'Artist', 'title': 'Title', 'track_number': 'Track', 'release_date_original': 'Date', 'duration': 'Time', 'maximum_sampling_rate': 'Format', }
#
#     info, track_all, play_index = append_song_info(dict_track, info_public, track_id, tracks)
#     return save_song_info_and_play(info, album_id, track_all, type=type)


def qobuz_play_album(playlistInfo, trackID, isAlbum=False, playType='w+', qobuz_manage=None, parameter=None, background_tasks=None):
    global qobuzPlayFlag
    # 遍历当前页歌曲 如果未找到播放链接则直接返回提示
    beforeData = []  # [{'tracks':list,'info':list}]  #保存前段部分
    afterData = []  # [{'tracks':list,'info':list}]  # 保存后段部分
    tempUrls = []  # 保存剩余部分
    flag = False  # 是否等于从此曲播放
    # 1.整专辑播放，加载第一页到播放列表，其他页后台加载
    # 2.从此曲目播放，for循环找到该曲目后，其余部分后台加载
    # offset = playlistInfo.get('tracks', {}).get('offset')
    limit = playlistInfo.get('tracks', {}).get('limit', 0)
    total = playlistInfo.get('tracks', {}).get('total', 0)
    otherPage = []  # 剩余的页数
    pages = int(total / limit) + 1
    print('播放列表页数：', pages, '总数：', total, '每页数量：', limit)
    for page in range(pages):
        if not flag:
            if page != 0:
                parameter['offset'] = page * limit
                # print(parameter['offset'], limit, page)
                path = os.path.join(cacheQobuzDir, allQobuzOrder[qobuz_manage]['path'].format(**parameter))
                playlistInfo = requestQobuz(allQobuzOrder[qobuz_manage]['url'], parameter, path)
            items = playlistInfo.get('tracks', {}).get('items', [])
            # print(json.dumps(playlistInfo))
            for item in items:
                itemID = item.get('id')
                # print(itemID, trackID, type(itemID), type(trackID))
                if itemID != trackID and not flag:
                    beforeData.append({'track': f'{vit_prefix}{itemID}', 'info': getTrackInfo(item, playlistInfo if isAlbum else None)})
                elif itemID == trackID or flag:
                    flag = True
                    afterData.append({'track': f'{vit_prefix}{itemID}', 'info': getTrackInfo(item, playlistInfo if isAlbum else None)})
            if not trackID:  # 没有指定歌曲，第一页跳出，其余部分异步加载
                flag = True
        else:
            otherPage.append(page)

    # print(afterData)
    # print(beforeData)
    if otherPage:
        data = afterData
    else:
        data = afterData + beforeData
    print('播放数量：', len(data), '首')
    save_song_info_and_play(data, playType)
    qobuzPlayFlag = time.time()
    if otherPage:
        background_tasks.add_task(qobuz_play_albumThread, otherPage, limit, isAlbum, qobuz_manage, parameter, qobuzPlayFlag, beforeData)

    return {'vit_status': 0, 'vit_message': ''}


def qobuz_play_albumThread(pages, limit, isAlbum, qobuz_manage, parameter, flag, infoData):
    global qobuzPlayFlag
    allData = []
    for page in pages:
        parameter['offset'] = page * limit
        # print(parameter['offset'], limit, page)
        path = os.path.join(cacheQobuzDir, allQobuzOrder[qobuz_manage]['path'].format(**parameter))
        playlistInfo = requestQobuz(allQobuzOrder[qobuz_manage]['url'], parameter, path)
        items = playlistInfo.get('tracks', {}).get('items', [])
        # print(json.dumps(playlistInfo))
        for item in items:
            itemID = item.get('id')
            # print(itemID, trackID, type(itemID), type(trackID))
            allData.append({'track': f'{vit_prefix}{itemID}', 'info': getTrackInfo(item, playlistInfo if isAlbum else None)})

    print(flag == qobuzPlayFlag, flag, qobuzPlayFlag)
    if flag == qobuzPlayFlag:
        allData = allData + infoData
        print('异步添加播放数量：', len(allData), '首')
        time.sleep(1)  # 等主线程读取完后再写入文件，此处可以改成随机临时文件名就不会有冲突
        save_song_info_and_play(allData, 'a+')


# def qobuz_play_playlist(params_dic, type):  # parameter 一般包含playlist_id和track_id 至少包含playlist_id
#
#     playlist_id = params_dic.get('playlist_id')
#     track_id = params_dic.get('track_id')
#     print(playlist_id, track_id)
#     try:
#         track_info = api.td_qobuz_playlist_get({'playlist_id': playlist_id, 'extra': 'tracks', 'limit': 500})
#         if track_info.get('vit_status') == 0:
#             tracks = track_info.get('tracks').get('items')
#         else:
#             return track_info
#     except:
#         return {"vit_status": 4, "vit_message": "888"}
#     dict_track = {'title': 'Title', "performer": 'Artist', 'album': 'Album', 'track_number': 'Track', 'release_date_original': 'Date',
#                   'cover': 'CoverPreview', 'maximum_sampling_rate': 'Format', 'duration': 'Time'}
#     info_public = ''
#
#     info, track_all, play_index = append_song_info(dict_track, info_public, track_id, tracks)
#     return save_song_info_and_play(info, playlist_id, track_all, type=type)

#
# def qobuz_play_seach_tracks(parameter_dic, type):
#     track_id = parameter_dic.get('track_id')
#     index = parameter_dic.get('track_index')  # 客户端传入的偏移量
#     total = parameter_dic.get('total')
#     query = parameter_dic.get('query')
#     if not track_id or not query:
#         return '{"vit_status":4,"vit_message":"444"}'
#
#     if not index or not index.isdigit():
#         index = 0
#
#     parameter_dic['offset'] = index
#     parameter_dic['limit'] = 100
#     return_tracks = int(total) - int(index) - 1  # 计算剩余的歌曲数目
#
#     if return_tracks > 100:
#
#         try:
#             track_info = api.td_qobuz_track_search({'query': query, 'limit': parameter_dic['limit'], 'offset': parameter_dic['offset']})
#
#
#         except Exception:
#             return '{"vit_status":4,"vit_message":"888"}'
#
#     else:
#         offset = int(parameter_dic['offset']) - (100 - return_tracks)
#         if offset < 0:
#             offset = 0
#         parameter_dic['offset'] = offset
#         track_info = api.td_qobuz_track_search({"query": query, 'limit': parameter_dic['limit'], 'offset': parameter_dic['offset']})
#     tracks = track_info.get('tracks').get('items')
#
#     dict_track = {'title': 'Title', "performer": 'Artist', 'label': 'Label', 'track_number': 'Track',
#                   'genre': 'Genre', 'album': 'Album', 'cover': 'CoverUncertainty', 'maximum_sampling_rate': 'Format',
#                   'duration': 'Time', 'releaseDate': 'Date', 'composer': 'Composer'}
#
#     info_public = ''
#     info, track_all, play_index = append_song_info(dict_track, info_public, track_id, tracks)
#
#     if -1 != play_index:
#         return save_song_info_and_play(info, track_id, track_all, type=type)
#
#     try:
#         track_info = api.td_qobuz_track_get({'track_id': track_id})
#         vit_status = track_info.get('vit_status')
#         if vit_status == 0:
#             playlist_add = track_info.get('id')
#             if playlist_add:
#                 track_url = f'{vit_prefix}{playlist_add}\n'
#                 track_all.insert(0, track_url)
#                 info += 'song_begin: {}'.format(track_url)
#
#                 dict_track = {'title': 'Title', "performer": 'Artist', 'track_number': 'Track', 'album': 'Album',
#                               'cover': 'Cover', 'maximum_sampling_rate': 'Format', 'duration': 'Time'}
#                 for key in dict_track.keys():
#                     if key == 'performer':
#                         value = track_info.get(key).get('name')
#                     elif key == 'album':
#                         value = track_info.get(key).get('title')
#                     elif 'cover' == key:
#                         value = track_info.get('album').get('image')
#                         cover = value.get('large')
#                         coverpreview = value.get('small')
#                         info += f'Cover: {cover}\nCoverPreview: {coverpreview}\n'
#                         continue
#                     elif 'maximum_sampling_rate' == key:
#                         sampling_rate = track_info.get('maximum_sampling_rate', '*')
#                         bit_depth = track_info.get('maximum_bit_depth', '*')
#                         channel_count = track_info.get('maximum_channel_count', '*')
#                         try:
#                             if float(sampling_rate) > 384:
#                                 byt = int(float(sampling_rate) * 100)
#                             else:
#                                 byt = int(float(sampling_rate) * 1000)
#                             value = f"{byt}:{bit_depth}:{channel_count}"
#                             if value == '*:*:*':
#                                 continue
#                         except:
#                             pass
#                     else:
#                         value = track_info.get(key)
#                     if not value:
#                         continue
#                     if key == 'duration':
#                         info += f'duration: {value}'
#                     info += '{}: {}\n'.format(dict_track[key], value)
#                 info += 'song_end\n'
#                 return save_song_info_and_play(info, track_id, track_all, type=type)
#         else:
#             return json.dumps(track_info)
#     except:
#         return '{"vit_status":4,"vit_message":"886"}'


# def qobuz_play_my_track(parameter_dic, type='w+'):  # parameter：必需包含track_id/track_index.
#
#     if isinstance(parameter_dic, str):
#         return '200'
#     try:
#         track_id = parameter_dic.get('track_id')
#         index = parameter_dic.get('track_index')  # 客户端传入的偏移量
#         total = parameter_dic.get('total')
#     except:
#         return '{"vit_status":4,"vit_message":"444"}'
#     if not index or not index.isdigit():
#         index = 0
#
#     parameter_dic['offset'] = index
#     parameter_dic['limit'] = 100
#     return_tracks = int(total) - int(index) - 1  # 计算剩余的歌曲数目
#
#     if return_tracks > 100:
#         try:
#             track_info = api.td_qobuz_favorite_getUserFavorites({"type": "tracks", 'limit': parameter_dic['limit'], 'offset': parameter_dic['offset']})
#
#         except Exception:
#             return '{"vit_status":4,"vit_message":"888"}'
#
#     else:
#         offset = int(parameter_dic['offset']) - (100 - return_tracks)
#         if offset < 0:
#             offset = 0
#         parameter_dic['offset'] = offset
#         track_info = api.td_qobuz_favorite_getUserFavorites({"type": "tracks", 'limit': parameter_dic['limit'], 'offset': parameter_dic['offset']})
#     tracks = track_info.get('tracks').get('items')
#
#     total = track_info.get('tracks').get('total')
#     # 如果收藏的歌曲大于等于100首而返回的歌曲不足一百首的话调整offset重新获取
#     if int(total) >= 100 and len(tracks) < 100:
#         parameter_dic['offset'] = int(parameter_dic['offset']) - (100 - len(tracks))
#         track_info = api.td_qobuz_favorite_getUserFavorites({"type": "tracks", 'limit': parameter_dic['limit'], 'offset': parameter_dic['offset']})
#         tracks = track_info.get('tracks').get('items')
#
#     dict_track = {'title': 'Title', "performer": 'Artist', 'label': 'Label', 'track_number': 'Track',
#                   'genre': 'Genre', 'album': 'Album', 'cover': 'CoverUncertainty', 'maximum_sampling_rate': 'Format',
#                   'duration': 'Time', 'releaseDate': 'Date', 'composer': 'Composer'}
#
#     info_public = ''
#     info, track_all, play_index = append_song_info(dict_track, info_public, track_id, tracks)
#     if -1 != play_index:
#         return save_song_info_and_play(info, track_id, track_all, type=type)
#
#     try:
#         track_info = api.td_qobuz_track_get({'track_id': track_id})
#         vit_status = track_info.get('vit_status')
#         if vit_status == 0:
#             playlist_add = track_info.get('id')
#             if playlist_add:
#                 track_url = f'{vit_prefix}{playlist_add}\n'
#                 track_all.insert(0, track_url)
#                 info += 'song_begin: {}'.format(track_url)
#
#                 dict_track = {'title': 'Title', "performer": 'Artist', 'track_number': 'Track', 'album': 'Album',
#                               'cover': 'Cover', 'maximum_sampling_rate': 'Format', 'duration': 'Time'}
#                 for key in dict_track.keys():
#                     if key == 'performer':
#                         value = track_info.get(key).get('name')
#                     elif key == 'album':
#                         value = track_info.get(key).get('title')
#                     elif 'cover' == key:
#                         value = track_info.get('album').get('image')
#                         cover = value.get('large')
#                         coverpreview = value.get('small')
#                         info += f'Cover: {cover}\nCoverPreview: {coverpreview}\n'
#                         continue
#                     elif 'maximum_sampling_rate' == key:
#                         sampling_rate = track_info.get('maximum_sampling_rate', '*')
#                         bit_depth = track_info.get('maximum_bit_depth', '*')
#                         channel_count = track_info.get('maximum_channel_count', '*')
#                         try:
#                             if float(sampling_rate) > 384:
#                                 byt = int(float(sampling_rate) * 100)
#                             else:
#                                 byt = int(float(sampling_rate) * 1000)
#                             value = f"{byt}:{bit_depth}:{channel_count}"
#                             if value == '*:*:*':
#                                 continue
#                         except:
#                             pass
#                     else:
#                         value = track_info.get(key)
#                     if not value:
#                         continue
#                     if key == 'duration':
#                         info += f'duration: {value}'
#                     info += '{}: {}\n'.format(dict_track[key], value)
#                 info += 'song_end\n'
#                 return save_song_info_and_play(info, track_id, track_all, type=type)
#     except:
#         return '{"vit_status":4,"vit_message":"886"}'


# 将歌曲信息存储起来，然后调用mpd的播放功能
def save_song_info_and_play(trackDatas, playType):
    """
    保持歌曲信息、mpc加载播放列表
    info:播放歌曲的信息
    track_all：需要加载的曲目
    playType：w+ 播放整个列表或专辑；a+ 添加到播放队列
    """
    track_all = [a['track'] for a in trackDatas]
    info = [a['info'] for a in trackDatas]
    info_dir = os.path.dirname(app_song_info)
    if not os.path.exists(info_dir):
        os.makedirs(info_dir)
    with open(app_song_info, playType, encoding='utf8') as f:
        f.write(''.join(info))
    with open(qobuz_m3u8_path, mode='w+', encoding='utf8') as f3:
        f3.write('\n'.join(track_all))
    if playType == 'w+':
        # 修改开始播放默认第一首歌 也就是客户端选中的那首歌 这样才不会在随机播放的模式下无法播放客户端选中的歌曲
        # os.system(f'{COMMAND_MPC} clear > /dev/null 2>&1 && {COMMAND_MPC} load {tidal_m3u8_path}  > /dev/null 2>&1 && {COMMAND_MPC} play 1 > /dev/null 2>&1')
        os.popen(f'{COMMAND_MPC} clear > /dev/null 2>&1 && {COMMAND_MPC} load {qobuz_m3u8_path}  > /dev/null 2>&1 && {COMMAND_MPC} play 1 > /dev/null 2>&1')
    elif playType == 'a+':
        os.popen(f'{COMMAND_MPC} load {qobuz_m3u8_path}  > /dev/null 2>&1')


def append_song_info(dict_track, info_public, track_id, tracks):
    play_index = -1
    info = ''
    track_all = []
    for index, track in enumerate(tracks):
        playlist_add = track.get('id')
        if not playlist_add:
            continue
        if str(track_id) == str(playlist_add):
            play_index = index
        track_url = f"{vit_prefix}{playlist_add}\n"

        if -1 == play_index:
            track_all.append(track_url)
        else:
            track_all.insert(index - play_index, track_url)

        info += 'song_begin: {}'.format(track_url)

        for key in dict_track.keys():
            if key == 'artist' or key == 'performer' or key == 'composer':
                value = track.get(key)
                if not value:
                    continue
                else:
                    value = value.get('name')
            elif 'cover' == key:
                value = track.get('album').get('image')
                cover = value.get('large')
                coverpreview = value.get('small')
                info += f'Cover: {cover}\nCoverPreview: {coverpreview}\n'
                continue
            elif key == 'album':
                value = track.get(key).get('title')
            elif 'release_date_original' == key:
                value = track.get('release_date_original')
                if not value:
                    value = track.get('album')
                    if not value:
                        continue
                    else:
                        value = value.get('release_date_original')


            else:
                value = track.get(key)
            if not value:
                continue
            mpd_key = dict_track[key]
            if 'maximum_sampling_rate' == key:
                sampling_rate = track.get('maximum_sampling_rate', '*')
                bit_depth = track.get('maximum_bit_depth', '*')
                channel_count = track.get('maximum_channel_count', '*')

                try:
                    if float(sampling_rate) > 384:
                        byt = int(float(sampling_rate) * 100)
                    else:
                        byt = int(float(sampling_rate) * 1000)
                    value = f"{byt}:{bit_depth}:{channel_count}"
                    if value == '*:*:*':
                        continue
                except:
                    pass
            if key == 'duration':
                info += f'duration: {value}\n'

            info += f'{mpd_key}: {value}\n'
        info += info_public + 'song_end\n'
    return info, track_all, play_index


def getTrackInfo(infoJson: dict, albumJson=None):
    """
    infoJson：曲目的json数据
    albumJson: 专辑数据
    注意：字符串':'后面有空格
    """
    # dict_track = {"performer": 'Artist', 'title': 'Title', 'track_number': 'Track', 'release_date_original': 'Date', 'duration': 'Time', 'maximum_sampling_rate': 'Format', }
    if albumJson:
        Cover = albumJson.get('image', {}).get('large', '')
        CoverPreview = albumJson.get('image', {}).get('small', '')
        Album = albumJson.get('label', {}).get('name', '')
        Artist = albumJson.get('artist', {}).get('name', '')
        Date = albumJson.get('release_date_original', '-')

    else:
        Cover = infoJson.get('album', {}).get('image', {}).get('large', '')
        CoverPreview = infoJson.get('album', {}).get('image', {}).get('small', '')
        Album = infoJson.get('album', {}).get('label', {}).get('name', '')
        Artist = infoJson.get('album', {}).get('artist', {}).get('name', '')
        Date = infoJson.get('album', {}).get('release_date_original', '-')

    Track = infoJson.get('track_number', '-')
    # Format = infoJson.get('maximum_sampling_rate', '-')
    sampling_rate = infoJson.get('maximum_sampling_rate', '*')
    bit_depth = infoJson.get('maximum_bit_depth', '*')
    channel_count = infoJson.get('maximum_channel_count', '*')
    Composer = infoJson.get('composer', '-')
    try:
        if float(sampling_rate) > 384:
            byt = int(float(sampling_rate) * 100)
        else:
            byt = int(float(sampling_rate) * 1000)
        value = f"{byt}:{bit_depth}:{channel_count}"
        Format = value
    except:
        Format = "*:*:*"

    strTemp = f"song_begin: {vit_prefix}{infoJson.get('id', '')}\n" + \
              f"Title: {infoJson.get('title', '')}\n" + \
              f"Artist: {Artist}\n" + \
              f"Track: {Track}\n" + \
              f"Format: {Format}\n" + \
              f"Album: {Album}\n" + \
              f"Composer: {Composer}\n" + \
              f"Date: {Date}\n" + \
              f"Cover: {Cover}\n" + \
              f"CoverPreview: {CoverPreview}\n" + \
              f"duration: {infoJson.get('date', '0')}\n" + \
              f"duration: {infoJson.get('duration', '0')}\n" + \
              f"Time: {infoJson.get('duration', '0')}\n" + \
              f"song_end\n"
    return strTemp


class Spoofer:
    def __init__(self, flag=False):
        self.seed_timezone_regex = r'[a-z]\.initialSeed\("(?P<seed>[\w=]+)",window\.utimezone\.(?P<timezone>[a-z]+)\)'
        # note: {timezones} should be replaced with every capitalized timezone joined by a |
        self.info_extras_regex = r'name:"\w+/(?P<timezone>{timezones})",info:"(?P<info>[\w=]+)",extras:"(?P<extras>[\w=]+)"'
        # self.appId_regex = r'{app_id:"(?P<app_id>\d{9})",app_secret:"\w{32}",base_port:"80",base_url:"https://www\.qobuz\.com",base_method:"/api\.json/0\.2/"},n\.base_url="https://play\.qobuz\.com"'
        self.appId_regex = r':\(n\.qobuzapi={app_id:"(?P<app_id>\d{9})",app_secret:"\w{32}",base_port:"80",base_url:"https://www\.qobuz\.com",base_method:"/api\.json/0\.2/"}'
        if flag or not os.path.exists(app_id_info):
            login_page_request = requests.get("https://play.qobuz.com/login",verify=False)
            login_page = login_page_request.text
            bundle_url_match = re.search(
                r'<script src="(/resources/\d+\.\d+\.\d+-[a-z]\d{3}/bundle\.js)"></script>',
                login_page,
            )
            bundle_url = bundle_url_match.group(1)
            bundle_req = requests.get("https://play.qobuz.com" + bundle_url,verify=False)
            self.bundle = bundle_req.text
            with open(app_id_info, 'w+') as f:
                 f.write(self.bundle)
            #print(self.bundle)
            #writeCacheFile(app_id_info,self.bundle)
        else:
            with open(app_id_info) as f:
                self.bundle = f.read()

    def getAppId(self):
        return re.search(self.appId_regex, self.bundle).group("app_id")

    def getSecrets(self):
        seed_matches = re.finditer(self.seed_timezone_regex, self.bundle)
        # 定义有序字典 有序字典可以按字典中元素的插入顺序来输出
        secrets = OrderedDict()
        for match in seed_matches:
            seed, timezone = match.group("seed", "timezone")
            secrets[timezone] = [seed]
        """The code that follows switches around the first and second timezone. Why? Read on:
            Qobuz uses two ternary (a shortened if statement) conditions that should always return false.
            The way Javascript's ternary syntax works, the second option listed is what runs if the condition returns false.
            Because of this, we must prioritize the *second* seed/timezone pair captured, not the first.
        """
        keypairs = list(secrets.items())
        secrets.move_to_end(keypairs[1][0], last=False)
        info_extras_regex = self.info_extras_regex.format(
            timezones="|".join([timezone.capitalize() for timezone in secrets])
        )
        info_extras_matches = re.finditer(info_extras_regex, self.bundle)
        for match in info_extras_matches:
            timezone, info, extras = match.group("timezone", "info", "extras")
            secrets[timezone.lower()] += [info, extras]
        for secret_pair in secrets:
            secrets[secret_pair] = base64.standard_b64decode(
                "".join(secrets[secret_pair])[:-44]
            ).decode("utf-8")
        return secrets


def response_data(status_code, detail):
    return HTTPException(status_code=status_code, detail=detail)


def _api_request(params, uri, appid):
    url = baseUrl + uri
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:67.0) Gecko/20100101 Firefox/67.0", 'X-App-Id': appid}
    session = requests.Session()
    print('params', params)
    print('headers', headers)
    try:
        r = session.post(url, data=params, headers=headers)
    except:
        return None
    print('_api_request', r.text)
    if r.status_code != 200:
        return None
    resp = json.loads(r.text)
    if resp.get('status', True) or resp.get('status') == None:
        return None
    print('_api_request', resp)
    return resp


def td_qobuz_Logout():
    info = ''
    skip_tidal = False
    try:
        os.system(f'{COMMAND_MPC} playlistdel http://online.silentangel.audio/qobuz > /dev/null 2>&1')
        with open(app_song_info, encoding='utf8') as f:
            for line in f:
                if line.startswith('song_begin: ' + vit_prefix):
                    skip_tidal = True
                if skip_tidal:
                    if line.startswith('song_end'):
                        skip_tidal = False
                    continue
                else:
                    info += line
        with open(app_song_info, 'w+', encoding='utf8') as f:
            f.write(info)
        setQobuzLoginStatus(False)
    except:
        pass

    if os.path.exists(info_path):
        clearCache('qobuz')  # 执行删除缓存
        try:
            delCacheFile(info_path)
            return {"vit_status": 0, "vit_message": ""}
        except:
            return {"vit_status": 1, "vit_message": '104'}

    else:
        return {"vit_status": 0, "vit_message": '0'}


# 存储用户信息。
def td_qobuz_userinfo_save(username, password_aes, userData):
    info_dir = os.path.dirname(info_path)
    if not os.path.exists(info_dir):
        os.makedirs(info_dir)
    with open(info_path, 'w+', encoding='utf8') as f:
        data_save = {'username': username, 'password': password_aes, 'userData': userData}
        f.write(json.dumps(data_save))


def userlib_getAlbums(appid, s4, ):
    ts = str(time.time())
    r_sig = f"userLibrarygetAlbumsList{ts}{s4}"
    r_sig_hashed = hashlib.md5(r_sig.encode("utf-8")).hexdigest()
    params = {
        "app_id": appid,
        "user_auth_token": None,
        "request_ts": ts,
        "request_sig": r_sig_hashed,
    }
    print('userlib_getAlbums', params)
    data = _api_request(params, '/userLibrary/getAlbumsList', appid)
    return data


def setSec(appid, spoofer: Spoofer, token):
    print(spoofer.getSecrets().values())
    for value in spoofer.getSecrets().values():
        s4 = value.encode('utf-8')
        if userlib_getAlbums(appid, s4) is not None:
            print("SECRET [%s]" % s4)
            return s4
    return s4


def td_qobuz_user_login(parameter, flag=False):  # 用户登录
    # try:
    ka = parameter
    password_aes = ka['password']
    ka['password'] = "".join(os.popen('{} {}'.format(thunder_aes_cbc128, ka['password'])).readlines()).strip()

    spoofer = Spoofer(flag=flag)
    appid = spoofer.getAppId()
    print('td_qobuz_user_login--appid', appid)
    print('td_qobuz_user_login--ka', ka)
    ka['app_id'] = appid
    data = td_qobuz_api_request(ka, '/user/login', login=True)
    print('td_qobuz_user_login--data', data)
    # if not data or not 'user' in data or not 'credential' in data['user'] \
    #         or not 'id' in data['user'] \
    #         or not 'parameters' in data['user']['credential']:
    #     # warn("/user/login returns %s" % data)
    #     self.logout()
    #     return json.du
    if data['vit_status'] == 0:
        user_auth_token = data['user_auth_token']
        s4 = setSec(appid, spoofer, user_auth_token)
        data['s4'] = s4.decode()
        data['appid'] = appid
        data['timestamp'] = str(int(time.time()))
        if not data["user"]["credential"]["parameters"]:
            pass  # 未订阅用户
        else:
            data['user']['email'] = ''
            data['user']['firstname'] = ''
            data['user']['lastname'] = ''
        td_qobuz_userinfo_save(username=ka['username'], password_aes=password_aes, userData=data)
        return {'vit_status': 0, 'vit_message': ''}
    else:
        return data

    # except:
    #    td_qobuz_user_login(parameter, flag=True)


def td_qobuz_maybe_login():  # 用户已登陆就从登陆信息中获取请求所需要的关键字段，

    user_playlist = td_qobuz_api_request({'limit': 1}, '/playlist/getUserPlaylists')
    vit_status = user_playlist.get('vit_status')
    if vit_status != 0:  # 如果副那会的vit_status不是0的话表示登陆已过期.
        return {"vit_status": 1, "vit_message": "101"}

    else:
        user_name = user_playlist.get('user', {}).get('login')
        return {"vit_status": 0, "vit_message": "", 'user': user_name}


def td_qobuz_relogin():
    if os.path.exists(info_path):
        try:
            with open(info_path) as f:
                data = json.load(f)
        except:
            delCacheFile(info_path)
            return {'vit_status': 4, 'vit_mesage': '446'}
        username = data.get('username', '')
        if not username:
            return {'vit_status': 2, 'vit_mesage': '201'}

        password = data.get('password', '')
        if not password:
            return {'vit_status': 2, 'vit_mesage': '202'}
        # parameter = f'username={username}&password={password}'
        parameter = {"username": username, "password": password}

        return td_qobuz_user_login(parameter)
    else:
        return {'vit_status': 1, 'vit_mesage': '101'}


# def writeCacheFile(path, jsonData):
#     if not Path(os.path.dirname(path)).is_dir():
#         os.makedirs(os.path.dirname(path).lower())  # 有同名的文件存在不能创建文件夹，需要改成小写
#
#     if len(os.path.basename(path)) < 255:  # 文件名不能大于255
#         with open(path, mode='w+', encoding='utf8') as f:
#             f.write(''.join(json.dumps(jsonData)))
#             f.close()


# def readFile(path):
#     data = {}
#     if Path(os.path.dirname(path)).is_dir():
#         with open(path, mode='w+', encoding='utf8') as f:
#             data = json.loads(f.read())
#             f.close()
#     return data


# def clearCache(day=-1, path=cacheQobuzDir, file="*"):  # 清除缓存,-1为全部，day天前的缓存数据
#     if day == -1:
#         os.popen(f'find {path} -type f  -name "{file}" -exec rm -rf {{}} \;')
#     else:
#         os.popen(f'find {path} -type f -mtime {day} -name "{file}" -exec rm -rf {{}} \;')


def asyncCache(url, datas, path, userFlag=False):
    """
    background_tasks.add_task(asyncCache, url)
    后台运行下载缓存
    asyncCacheList：缓存列表，如果有缓存在运行，就退出
    """
    print('异步刷新或下载缓存:', url, datas)
    data = requestQobuz(url, datas, path, isRefresh=1, userFlag=userFlag)
    if data['vit_status'] == 0:  # 如果获取到数据
        writeCacheFile(path, data)


def loadL2Cache(path, isL2Cache, datas, url, ):
    """
    二级缓存
    :param path: 缓存的文件路径
    :param isL2Cache: 是否二级缓存，-1:不执行，0：执行下一页，1~20：缓存1-20个，99缓存全部
    :return: 不返回数据，将需要缓存的url添加到cacheList列表，让线程执行
    """
    global cacheQobuzList
    if isL2Cache == 99:
        isL2Cache = 1000
    if os.path.exists(path):
        with open(path, mode='r+', encoding='utf8') as f:
            readData = f.read()
            f.close()
        try:
            jsonData = json.loads(readData)
        except:
            pass
        if jsonData.get('vit_status') == 0:
            nextInfo = None
            albums = jsonData.get('albums', {})
            if albums:
                nextInfo = albums.copy()
                loadNextPage(nextInfo, url, datas, targetType='albums')
                for item in albums.get('items', [])[isL2Cache::-1]:
                    parameter = {'album_id': item.get('id')}
                    pathAlbum = os.path.join(cacheQobuzDir, allQobuzOrder['album_detail']['path'].format(**parameter))
                    tempData = {'parameter': parameter, 'url': allQobuzOrder['album_detail']['url'], 'path': pathAlbum}
                    if tempData not in cacheQobuzList and len(cacheQobuzList) < cacheListLimit:
                        cacheQobuzList.append(tempData)

                        # print('and to cacheQobuzList', tempData, len(cacheQobuzList))
            playlists = jsonData.get('playlists', {})
            # print('playlists items', len(playlists.get('items', [])))
            if playlists:
                nextInfo = playlists.copy()
                loadNextPage(nextInfo, url, datas, targetType='playlists')
                for item in playlists.get('items', [])[isL2Cache::-1]:
                    parameter = {'playlist_id': item.get('id'), 'extra': 'tracks', 'offset': 0, 'limit': 500}
                    pathPlaylist = os.path.join(cacheQobuzDir, allQobuzOrder['playlist_detail']['path'].format(**parameter))
                    # if not isQobuzCacheActive(path):
                    tempData = {'parameter': parameter, 'url': allQobuzOrder['playlist_detail']['url'], 'path': pathPlaylist}
                    if tempData not in cacheQobuzList and len(cacheQobuzList) < cacheListLimit:
                        cacheQobuzList.append(tempData)
                        # print('and to cacheQobuzList', tempData, len(cacheQobuzList))
            tracks = jsonData.get('tracks', {})
            # print('playlists items', len(playlists.get('items', [])))
            if tracks:
                nextInfo = tracks.copy()
                loadNextPage(nextInfo, url, datas, targetType='tracks')
            artists = jsonData.get('artists', {})
            if artists:
                nextInfo = artists.copy()
                loadNextPage(nextInfo, url, datas, targetType='artists')
            # ------------------------------------首页等特殊页面的缓存-------------------------------------------------
            containers = jsonData.get('containers')
            items = ['container-album-new-releases','container-featuredPlaylists','container-explore','container-album-new-releases-full','container-album-recent-releases',
                   'container-album-press-awards','container-album-charts'] # 首页-新发行，首页-qobuz歌单，首页-qobuz风格，新发行-全部，新发行-流行中，新发行-媒体好评，新发行-热门发行
            if containers:  # index 页面、新发型
                for item in items:
                    tempJson = containers.get(item)  # 新发行
                    if tempJson:
                        if item == 'container-featuredPlaylists':
                            isL2Cache = isL2Cache*2
                        load2LCacheIndex(tempJson, isL2Cache)



def load2LCacheIndex(jsonData, isL2Cache):
    albums = jsonData.get('albums', {})
    if albums:
        for item in albums.get('items', [])[isL2Cache::-1]:
            parameter = {'album_id': item.get('id')}
            pathAlbum = os.path.join(cacheQobuzDir, allQobuzOrder['album_detail']['path'].format(**parameter))
            tempData = {'parameter': parameter, 'url': allQobuzOrder['album_detail']['url'], 'path': pathAlbum}
            if tempData not in cacheQobuzList and len(cacheQobuzList) < cacheListLimit:
                cacheQobuzList.append(tempData)
    playlists = jsonData.get('playlists', {})
    if playlists:
        for item in playlists.get('items', [])[isL2Cache::-1]:
            parameter = {'playlist_id': item.get('id'), 'extra': 'tracks', 'offset': 0, 'limit': 500}
            pathPlaylist = os.path.join(cacheQobuzDir, allQobuzOrder['playlist_detail']['path'].format(**parameter))
            tempData = {'parameter': parameter, 'url': allQobuzOrder['playlist_detail']['url'], 'path': pathPlaylist}
            if tempData not in cacheQobuzList and len(cacheQobuzList) < cacheListLimit:
                cacheQobuzList.append(tempData)
    artists = jsonData.get('artists', {})


def loadNextPage(target, url, datas, targetType=None):
    # print(url, allQobuzOrder.get('catalog_search').get('url'))
    if url == allQobuzOrder.get('catalog_search').get('url'):
        if 'tracks' == targetType:
            url = allQobuzOrder.get('track_search').get('url')
        if 'albums' == targetType:
            url = allQobuzOrder.get('album_search').get('url')
        if 'artists' == targetType:
            url = allQobuzOrder.get('artist_search').get('url')
        if 'playlists' == targetType:
            url = allQobuzOrder.get('playlist_search').get('url')
    try:
        offset = target.get('offset')
        limit = target.get('limit')
        total = target.get('total')
    except:
        return
    if not offset or not limit or not total:
        return
    if total > limit + offset:
        dataKey = None
        for key in allQobuzOrder.keys():
            if allQobuzOrder.get(key).get('url') == url:
                dataKey = key
        if dataKey in ['get_user_playlists']:
            userFlag = True
        else:
            userFlag = False
        nextObj = datas.copy()
        nextObj['offset'] = limit + offset
        playlistPath = os.path.join(cacheQobuzDir, allQobuzOrder[dataKey]['path'].format(**nextObj))
        print('playlistPath:', playlistPath, dataKey, url)
        if not isQobuzCacheActive(playlistPath):
            playlistData = td_qobuz_api_request(nextObj, allQobuzOrder[dataKey].get('url'), userFlag=userFlag)
            if playlistData['vit_status'] == 0:
                writeCacheFile(playlistPath, playlistData)

        # entries = jsonData.get('content', {}).get('entries', [])
        # if isL2Cache > 0:
        #     count = 0
        #     for data in entries:
        #         if count == isL2Cache:
        #             break
        #         count += 1
        #         url = data.get('url')
        #         if url:
        #             if 'album' in url or 'playlist' in url:  # 只对播放列表和专辑进行缓存
        #                 if len(cacheTidalList) < cacheListLimit and url not in cacheTidalList:
        #                     cacheTidalList.append(url)
        #                     print("add url:{} to cacheTidalList, time:{}".format(url, time.time()))


def requestQobuz(url, datas, path, isRefresh=0, cacheTime=cacheDefaultTime, isL2Cache=-1, background_tasks=None, userFlag=False):
    """
    sRefresh:是否强制刷新
    cacheTime：缓存时间
    isL2Cache是否缓存
    """

    if os.path.exists(path) and isRefresh == 0:
        mtime = os.stat(path).st_mtime  # 获取文件的修改时间
        try:
            with open(path, mode='r+', encoding='utf8') as f:
                readData = json.loads(f.read())
                f.close()
            print('读取缓存')
            if abs(int(time.time() - mtime)) < cacheTime:
                if isL2Cache > -1 and background_tasks is not None:
                    background_tasks.add_task(loadL2Cache, path, isL2Cache, datas, url, )  # 二级缓存队列
                if background_tasks is not None:  # 搜索页面不刷新缓存
                    background_tasks.add_task(asyncCache, url, datas, path, userFlag)
                return readData
        except:
            # 读取缓存出错后，直接请求网络
            logger.exception("What?!")
            pass
    data = td_qobuz_api_request(datas, url, userFlag=userFlag)
    print('请求Qobuz:', url, datas)
    if data['vit_status'] in [0]:  # 如果获取到数据
        writeCacheFile(path, data)
    else:
        delCacheFile(path)
    if isL2Cache > -1 and background_tasks is not None:
        background_tasks.add_task(loadL2Cache, path, isL2Cache, datas, url, )  # 二级缓存队列
    # if background_tasks is not None:  # 加载下一页
    #     background_tasks.add_task(cacheNextPage, data)
    return data


def getGenreIDs(parameter: dict):
    data = {'genre_ids': None}
    ids = parameter.get('genres_ids')
    if not ids:
        ids = parameter.get('genre_ids')
    if ids:
        ids = ids.split(',')
        arr = [int(n) for n in ids]
        arr.sort()
        ids = [str(id1) for id1 in arr]
        data['genre_ids'] = ','.join(ids)
    return data


def resetGenreIDs(ids):
    data = {'genre_ids': None}
    if ids:
        ids = ids.split(',')
        arr = [int(n) for n in ids]
        arr.sort()
        ids = [str(id1) for id1 in arr]
        data['genre_ids'] = ','.join(ids)
    return data


def actionPlaylist(parameterDic, url, isRefresh, background_tasks):
    delCacheFile(os.path.join(cacheQobuzDir, "index/getUserPlaylists*"))  # 删除缓存
    delCacheFile(os.path.join(cacheQobuzDir, "playlist/{}_offset*".format(parameterDic.get('playlist_id', ''))))
    if isRefresh == 1:
        data = td_qobuz_api_request(parameterDic, url)  # 执行后，后台缓存我的播放列表和该播放列表
        parameterDic = {}
        background_tasks.add_task(actionPlaylistBackground, parameterDic, url)
        return data
    else:
        background_tasks.add_task(actionPlaylistBackground, parameterDic, url)  # 后台执行，并再缓存我的播放列表和该播放列表
        return {'vit_status': 0, 'vit_message': ''}


def actionPlaylistBackground(parameterDic, url):
    if parameterDic:
        td_qobuz_api_request(parameterDic, url)
    tmpParameter = {'offset': '0', 'limit': '500'}
    path = os.path.join(cacheQobuzDir, allQobuzOrder['get_user_playlists']['path'].format(**tmpParameter))
    print(path)
    requestQobuz(allQobuzOrder['get_user_playlists']['url'], tmpParameter, path, userFlag=True)
    tmpParameter = {'offset': '0', 'limit': '500', 'playlist_id': parameterDic.get('playlist_id'), 'extra': 'tracks'}
    path = os.path.join(cacheQobuzDir, allQobuzOrder['playlist_detail']['path'].format(**tmpParameter))
    print(path)
    requestQobuz(allQobuzOrder['playlist_detail']['url'], tmpParameter, path)


def actionFavorite(parameterDic, url, isRefresh, background_tasks):
    delCacheFile(os.path.join(cacheQobuzDir, "favorite/getUserFavorites_type*None*"))  # 删除缓存
    print(parameterDic)
    if parameterDic.get('album_ids'):
        typeFavorite = 'albums'
        delCacheFile(os.path.join(cacheQobuzDir, "favorite/getUserFavorites_type*albums*"))
    elif parameterDic.get('track_ids'):
        typeFavorite = 'tracks'
        delCacheFile(os.path.join(cacheQobuzDir, "favorite/getUserFavorites_type*tracks*"))
    elif parameterDic.get('artist_ids'):
        typeFavorite = 'artists'
        delCacheFile(os.path.join(cacheQobuzDir, "favorite/getUserFavorites_type*artists*"))
    else:
        return {'vit_status': 0, 'vit_message': ''}
    delCacheFile(os.path.join(cacheQobuzDir, "favorite/getUserFavoriteIds"))
    if isRefresh == 1:
        return td_qobuz_api_request(parameterDic, url)
    else:
        background_tasks.add_task(actionFavoriteBackground, parameterDic, url, typeFavorite)
        return {'vit_status': 0, 'vit_message': ''}


def actionFavoriteBackground(parameterDic, url, typeFavorite):
    if parameterDic:
        td_qobuz_api_request(parameterDic, url)
    tmpParameter = {'offset': '0', 'limit': '9', 'type': None}
    path = os.path.join(cacheQobuzDir, allQobuzOrder['get_User_Favorites']['path'].format(**tmpParameter))
    print(path)
    requestQobuz(allQobuzOrder['get_User_Favorites']['url'], tmpParameter, path, userFlag=True)
    if typeFavorite == 'tracks':
        limit = 500
    else:
        limit = 30
    tmpParameter = {'offset': '0', 'limit': limit, 'type': typeFavorite}
    path = os.path.join(cacheQobuzDir, allQobuzOrder['get_User_Favorites']['path'].format(**tmpParameter))
    print(path)
    requestQobuz(allQobuzOrder['get_User_Favorites']['url'], tmpParameter, path)


def delCacheFile(file):  # 清除文件
    a = os.popen('rm -f {}'.format(file))
    print('删除缓存路径：', file, a)


def isQobuzCacheActive(path):  # url缓存是否有效
    if os.path.exists(path):
        mtimeUrl = os.stat(path).st_mtime  # 获取文件的修改时间
        # print(time.time(),mtimeUrl,int(time.time() - mtimeUrl),cacheTimeout)
        if abs(int(time.time() - mtimeUrl)) < cacheTimeout:  # 小于跳过
            return True
    return False


def getQobuzHomepage():
    global isQobuzLogin
    global cacheQobuzList
    while True:
        if isQobuzLogin:
            sizeTmp = getDirSize(cacheQobuzDir)
            print("qobuz缓存大小：{}M".format(int(sizeTmp / 1000 / 1000)))
            if sizeTmp > 1000 * 1000 * 1000:  # 缓存大于1G，清除7天前的数据
                clearCache('qobuz', day=7)
            for key in allQobuzOrder.keys():
                caches = allQobuzOrder[key].get('cache', [])
                userInfo = readFile(info_path)  # 读取用户信息
                user_id = userInfo.get('userData', {}).get('user', {}).get('id')  # 获取用户id
                if key in ['get_user_playlists']:  # 下一页也使用了userFlag，移动到此处，避免报错
                    userFlag = True
                else:
                    userFlag = False
                if not user_id:
                    break
                objs = []
                for cache in caches:
                    if 'genre_ids' in cache.keys():
                        tmpList = []
                        genreInfo = readFile(qobuzGenreIds)  # 读取存储的genreInfo
                        tmpList.append(None)
                        tmpList.append(genreInfo.get('android', {}).get('genre_ids', None))
                        tmpList.append(genreInfo.get('ios', {}).get('genre_ids', None))
                        tmpList = list(set(tmpList))  # 去重复

                        for tmp in tmpList:
                            cache['genre_ids'] = tmp
                            objs.append(cache.copy())
                    elif 'user_id' in cache.keys():
                        cache['user_id'] = user_id
                        objs.append(cache.copy())
                    else:
                        objs.append(cache.copy())
                for obj in objs:
                    # wiatListAndApp()
                    path = os.path.join(cacheQobuzDir, allQobuzOrder[key]['path'].format(**obj))
                    status = isQobuzCacheActive(path)
                    print('是否有效(qobuz):', status, path)
                    if status:
                        with open(path, mode='r+', encoding='utf8') as f:
                            tmpData = f.read()
                            f.close()
                            try:
                                data = json.loads(tmpData)
                            except:
                                print(path, 'not is json')
                                continue
                    else:
                        data = td_qobuz_api_request(obj, allQobuzOrder[key].get('url'), userFlag=userFlag)
                        if data['vit_status'] == 1:
                            print('Qobuz没有登录')
                            break
                        elif data['vit_status'] == 0:
                            writeCacheFile(path, data)
                    # except Exception:
                    #      print(Exception)
                    #      continue
                    if data.get('vit_status') == 0:
                        # tracks = data.get('tracks',[])
                        nextPage = None
                        albums = data.get('albums', {})

                        # print('albums items',len(albums.get('items', [])))
                        if albums:
                            nextPage = albums.copy()
                            for item in albums.get('items', [])[::-1]:
                                parameter = {'album_id': item.get('id')}
                                pathAlbum = os.path.join(cacheQobuzDir, allQobuzOrder['album_detail']['path'].format(**parameter))
                                tempData = {'parameter': parameter, 'url': allQobuzOrder['album_detail']['url'], 'path': pathAlbum}
                                if tempData not in cacheQobuzList and len(cacheQobuzList) < cacheListLimit:
                                    cacheQobuzList.append(tempData)
                                    # print('and to cacheQobuzList',tempData,len(cacheQobuzList) )
                        playlists = data.get('playlists', {})
                        # print('playlists items', len(playlists.get('items', [])))
                        if playlists:
                            nextPage = playlists.copy()
                            for item in playlists.get('items', [])[::-1]:
                                parameter = {'playlist_id': item.get('id'), 'extra': 'tracks', 'offset': 0, 'limit': 500}
                                pathPlaylist = os.path.join(cacheQobuzDir, allQobuzOrder['playlist_detail']['path'].format(**parameter))
                                # if not isQobuzCacheActive(path):
                                tempData = {'parameter': parameter, 'url': allQobuzOrder['playlist_detail']['url'], 'path': pathPlaylist}
                                if tempData not in cacheQobuzList and len(cacheQobuzList) < cacheListLimit:
                                    cacheQobuzList.append(tempData)
                                    # print('and to cacheQobuzList', tempData, len(cacheQobuzList))
                            # 下一页
                        if nextPage:
                            limit = nextPage.get('limit', 0)
                            total = nextPage.get('total', 0)
                            if total > limit:
                                nextObj = obj.copy()
                                nextObj['offset'] = limit
                                playlistPath = os.path.join(cacheQobuzDir, allQobuzOrder[key]['path'].format(**nextObj))
                                if not isQobuzCacheActive(playlistPath):
                                    playlistData = td_qobuz_api_request(nextObj, allQobuzOrder[key].get('url'), userFlag=userFlag)
                                    if playlistData['vit_status'] == 0:
                                        writeCacheFile(playlistPath, playlistData)
                    time.sleep(random.randint(10, 30) * 0.1)
            time.sleep(120)
        time.sleep(1)


def cacheQobuzQueue():
    global appVisitTime
    global cacheQobuzList
    global isQobuzLogin
    while True:
        while abs(int(time.time() - appVisitTime)) < 5:  # cacheTidalList有队列 和 有点击动作
            time.sleep(1)
        if cacheQobuzList and isQobuzLogin:
            obj = cacheQobuzList.pop(-1)  # 先进先出
            if not obj:
                continue
            path = obj.get('path')
            url = obj.get('url')
            parameter = obj.get('parameter')
            if os.path.exists(path):
                mtimeUrl = os.stat(path).st_mtime  # 获取文件的修改时间
                if abs(int(time.time() - mtimeUrl)) < cacheTimeout:  # 小于跳过
                    continue
            try:
                data = td_qobuz_api_request(parameter, url)
                if data['vit_status'] == 1:
                    cacheQobuzList = []
                elif data['vit_status'] == 0:
                    writeCacheFile(path, data)
                print("cacheQobuzList[{}] pop, time:{}".format(len(cacheQobuzList), time.time()))
            except:
                continue
            if data['vit_status'] in [0]:  # 如果获取到数据
                writeCacheFile(path, data)
        time.sleep(random.randint(10, 20) * 0.1)


def initQobuzFun():
    # 主页
    tmpList = []
    genreInfo = readFile(qobuzGenreIds)  # 读取存储的genreInfo
    tmpList.append(None)
    tmpList.append(genreInfo.get('android', {}).get('genre_ids', None))
    tmpList.append(genreInfo.get('ios', {}).get('genre_ids', None))
    tmpList = list(set(tmpList))  # 去重复
    for tmp in tmpList:
        parameter = {'genre_ids': tmp}
        path = os.path.join(cacheQobuzDir, allQobuzOrder['index']['path'].format(**parameter))
        requestQobuz(allQobuzOrder['index']['url'], parameter, path)
    # 我的播放列表
    parameter = {'offset': 0, 'limit': 500}
    path = os.path.join(cacheQobuzDir, allQobuzOrder['get_user_playlists']['path'].format(**parameter))
    requestQobuz(allQobuzOrder['get_user_playlists']['url'], parameter, path)


def getTrachUrl(format_id, intent, track_id):
    if os.path.exists(qobuzServerTime):  # 如果文件存在则表示用户登陆过
        with open(qobuzServerTime) as f:
            tsInfo = json.load(f)
            f.close()
            ts = str(int(time.time()) + tsInfo.get('serverTime') - tsInfo.get('nowTime'))
    else:
        ts = str(time.time())
    print(ts)
    if os.path.exists(info_path):  # 如果文件存在则表示用户登陆过
        with open(info_path) as f:
            userInfo = json.load(f)
            f.close()
    else:
        return {'vit_status': 4, 'vit_message': 'login is fail'}
    s4 = userInfo.get('userData', {}).get('s4', '').encode('ASCII')
    # print('s4', s4)

    stringvalue = f'trackgetFileUrlformat_id{format_id}intent{intent}track_id{track_id}{ts}'
    stringvalue = stringvalue.encode('ASCII')
    # print('stringvalue', stringvalue)
    stringvalue += s4
    rq_sig = str(hashlib.md5(stringvalue).hexdigest())
    params = {'format_id': f'{format_id}',
              'intent': intent,
              'request_ts': ts,
              'request_sig': rq_sig,
              'track_id': f'{track_id}'
              }
    data = td_qobuz_api_request(params, '/track/getFileUrl')
    return data
