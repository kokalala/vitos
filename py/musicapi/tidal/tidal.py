import os

from fastapi import APIRouter, Request
from tidal.tidalFun import *
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/python/tidal", tags=["tidal"], include_in_schema=False)
def read_data(request: Request, background_tasks: BackgroundTasks, isRefresh: int = -1, cacheTime: int = cacheDefaultTime, isL2Cache: int = -1):  # async
    """

    :param request:
    :param background_tasks:
    :param isRefresh: 是否强制刷新
    :param cacheTime: 缓存时间
    :param isL2Cache: -1:不缓存，0：缓存下一页，1~20缓存数量+下一页，99全部缓存
    :return:
    """

    if isRefresh == -1:
        isRefresh = 0
        actionsFlag = 1  # 收藏是否前台执行
    else:
        actionsFlag = isRefresh
    tidal_manage = request.query_params.get('tidal_manage')
    parameterDic = request.query_params
    # print('parameterDic', parameterDic, )

    if tidal_manage in allTidalOrder.keys():
        if allTidalOrder.get(tidal_manage) != "":  # 是否访问url
            try:
                url = allTidalOrder.get(tidal_manage).format(**parameterDic)  # 传参到url
            except Exception as e:
                return {'vit_status': 4, 'vit_message': '201', "msg": "参数错误"}
            data = requestAirable(url, isRefresh=isRefresh, cacheTime=cacheTime, isL2Cache=isL2Cache, background_tasks=background_tasks)

            return data
    if tidal_manage == "asyncExec":  # 异步执行url
        url = parameterDic.get('url')
        getUrl(url)
        if "r=/" in unquote(url):  # id/tidal/ablbum/221962069
            tmpPath = unquote(url).split('r=/')[1]
            background_tasks.add_task(asyncCache, tmpPath)  # 异步加载缓存

    # ------------------------------------------------ 搜索 -------------------------------------------------------------
    elif tidal_manage in ["seach_albums", "seach_playlists", "seach_tracks", "seach_artists"]:
        return seachTidal(parameterDic, isRefresh, cacheTime, isL2Cache, background_tasks)

    elif tidal_manage == "common":
        url = parameterDic.get('url')
        if not url:
            return {'vit_status': 2, 'vit_message': '201'}
        if "actions/tidal" in url and 'favorites' in url:  # 收藏专辑、歌曲、播放列表
            if actionsFlag == 0:
                actionsFavorites(url, background_tasks=background_tasks)
            else:
                requestAirable(url, isRefresh=1)
            return {'vit_status': 0, 'vit_message': '0'}
        data = requestAirable(url, isRefresh=isRefresh, cacheTime=cacheTime, isL2Cache=isL2Cache, background_tasks=background_tasks)
        return data

    elif tidal_manage == "insert_playlist":  # 收藏曲目到播放列表
        url = "https://meta.airable.io/actions/tidal/track/{track_id}/playlist/{id}/insert".format(**parameterDic)
        playlistID = parameterDic.get('id', '')
        delCacheFile("id/tidal/playlist/{}".format(playlistID))  # 删除缓存
        delCacheFile("tidal/my/playlists*")  # 删除缓存
        if actionsFlag == 0:
            background_tasks.add_task(asyncExec, "{}?{}".format(url, quote('r=/{}'.format(allTidalOrder['my_playlists'].split(airableHost)[1]))))
        else:
            requestAirable(url, isRefresh=1)
        return {'vit_status': 0, 'vit_message': '0'}

    elif tidal_manage == "insert_new_playlist":  # 收藏曲目到新的播放列表
        url = "https://meta.airable.io/actions/tidal/track/{track_id}/playlist/new/insert?name={playlist_name}".format(**parameterDic)
        if actionsFlag == 0:
            background_tasks.add_task(asyncExec, url)
        else:
            requestAirable(url, isRefresh=1)
        delCacheFile("tidal/my/playlists*")  # 删除缓存
        return {'vit_status': 0, 'vit_message': '0'}

    # ------------------------------------------------登录状态/登出------------------------------------------------------
    elif tidal_manage == "initTidal":  # 用户登录后，调用该接口
        print('initTidal')
        background_tasks.add_task(initTidal)
        setTidalLoginStatus(True)
        return {'vit_status': 0, 'vit_message': ''}

    elif tidal_manage == 'quality_set':  # 设置播放音质
        quality = parameterDic.get('quality')
        return quality_set(quality)

    # ------------------------------------------------登录状态/登出------------------------------------------------------
    elif tidal_manage == 'login_and_quality':  # 查询登录状态和音质设置
        return tidal_login_and_quality()
    elif tidal_manage == 'logout':
        return tidal_logout()
    # -----------------------------------------------播放-------------------------------------------------------------------
    elif tidal_manage == 'track_url':  # 获取曲目的播放url，弃用
        try:
            with open(quality_info) as f:
                quality = f.read()
            if not quality:
                quality = 'Master'
        except:
            quality = 'Master'
        url = getPlayUrl(parameterDic, background_tasks, quality=quality)
        return url


    elif tidal_manage == 'add_track':  # 添加到播放队列
        res = tidal_add_track(parameterDic, background_tasks)
        return res

    elif tidal_manage == 'play_album':  # 播放整张专辑
        track_url = parameterDic.get('track_url')
        playlist_url = parameterDic.get('album_url')
        res = playListOrAlbum(playlist_url, 'w+', track_url, background_tasks)
        return res

    elif tidal_manage == 'play_playlist':  # 播放列表 从这里开始播放
        track_url = parameterDic.get('track_url')
        playlist_url = parameterDic.get('playlist_url')
        res = playListOrAlbum(playlist_url, 'w+', track_url, background_tasks)
        return res

    elif tidal_manage == 'play_my_track':  # 播放我的收藏曲目
        playlist_url = 'https://meta.airable.io/tidal/my/tracks?p={}&s=a-z'
        track_url = parameterDic.get('track_url')
        res = playListOrAlbum(playlist_url, 'w+', track_url, background_tasks)
        return res

    elif tidal_manage == 'playlist_add_album':  # 将专辑添加到播放队列
        playlist_url = parameterDic.get('album_url')
        res = playListOrAlbum(playlist_url, 'a+', None, background_tasks)
        return res

    elif tidal_manage == 'playlist_add_playlist':  # 将播放列表添加到播放队列
        playlist_url = parameterDic.get('playlist_url')
        res = playListOrAlbum(playlist_url, 'a+', None, background_tasks)
        return res

    elif tidal_manage == 'play_artist_track':  # 艺术家->曲目->从这里开始播放
        # return tidal_play_artist_tracks(parameterDic, type='w+')
        track_url = parameterDic.get('track_url')
        playlist_url = parameterDic.get('url')
        res = playListOrAlbum(playlist_url, 'w+', track_url, background_tasks)
        return res

    elif tidal_manage == 'play_new_tracks':  # 播放首页的曲目列表
        playlist_url = "https://meta.airable.io/tidal/new/tracks?p=1"
        track_url = parameterDic.get('track_url')
        res = playListOrAlbum(playlist_url, 'w+', track_url, background_tasks)
        return res
    elif tidal_manage == 'play_rising_tracks':  # 播放曲目列表
        playlist_url = "https://meta.airable.io/tidal/rising/tracks?p=1"
        track_url = parameterDic.get('track_url')
        res = playListOrAlbum(playlist_url, 'w+', track_url, background_tasks)
        return res
        # return tidal_play_hundred_tracks(parameterDic, url=url, type='w+')

    elif tidal_manage == 'play_top_tracks':  # 曲风 - > 曲目
        track_url = parameterDic.get('track_url')
        playlist_url = parameterDic.get('url')
        res = playListOrAlbum(playlist_url, 'w+', track_url, background_tasks)
        return res
    else:
        return {"vit_status": 98, "vit_message": "987"}


@router.get("/python/tidal/track_url", tags=["tidal"], response_class=HTMLResponse, include_in_schema=False)
def track_url(request: Request):  # async
    """
        通过曲目id路径返回播放的url
    """
    track_id = request.query_params.get('track_id')
    try:
        with open(quality_info) as f:
            quality = f.read()
        if not quality:
            quality = 'Master'
    except:
        quality = 'Master'
    url = getPlayUrl(track_id, quality=quality)
    # TODO 非付费用户，没有streams，需要判断，amazon同理
    return url


@router.get("/tidal", tags=["tidal"], summary='播放链接')  # test
def proxy_api(url: str):  # async
    """
    播放器直接播放url，重定向返回播放地址
    """

    try:
        with open(quality_info) as f:
            quality = f.read()
        if not quality:
            quality = 'Master'
    except:
        quality = 'Master'
    playUrl = getPlayUrl(url, quality=quality)
    response = RedirectResponse(url=playUrl)
    return response
#
#
# @router.get("/python/tidal/play/{postion}", tags=["tidal"])  # test
# def proxy_api1(postion: int):  # async
#     print('postion', postion)
#     if postion:
#         # os.popen(f"mpc stop > /dev/null 2>&1 && mpc play {postion}  > /dev/null 2>&1")
#         command1 = os.popen('systemctl restart mpd').readlines()
#         print('systemctl restart mpd:', ''.join(command1))
#
#         command2 = os.popen(f'mpc play {postion + 1}').readlines()
#         print('mpc play:', ''.join(command2))
#
#     return {"vit_status": 0, "vit_message": ""}
