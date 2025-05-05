import os

from fastapi import APIRouter, Request,BackgroundTasks
from amazon.amazonFun import *
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/python/amazon", tags=["amazon"],include_in_schema=False)
def read_data(request: Request, background_tasks: BackgroundTasks, isRefresh: int = 0, cacheTime: int = cacheDefaultTime, isL2Cache: int = -1):  # async
    """
    主入口
    :param request:
    :param background_tasks:
    :param isRefresh: 是否强制刷新
    :param cacheTime: 缓存时间
    :param isL2Cache: -1:不缓存，0：缓存下一页，1~20缓存数量+下一页，99全部缓存
    :return:
    """
    amazon_manage = request.query_params.get('amazon_manage')
    parameterDic = request.query_params

    if amazon_manage in allAmazonOrder.keys():
        if allAmazonOrder.get(amazon_manage) != "":  # 是否访问url
            try:
                url = allAmazonOrder.get(amazon_manage).format(**parameterDic)  # 传参到url
            except Exception as e:
                return {'vit_status': 4, 'vit_message': '201', "msg": "参数错误"}
            data = requestAirable(url, isRefresh=isRefresh, cacheTime=cacheTime, isL2Cache=isL2Cache, background_tasks=background_tasks)
            return data

    if amazon_manage == "asyncExec":  # 异步执行url,主要是收藏等
        url = parameterDic.get('url')
        getUrl(url)
        if "r=/" in unquote(url):  # id/tidal/ablbum/221962069
            tmpPath = unquote(url).split('r=/')[1]
            background_tasks.add_task(asyncCache, tmpPath)  # 异步加载缓存
    elif amazon_manage == 'maybe_login':
        return maybe_login()
    # ------------------------------------------------ 搜索 -------------------------------------------------------------
    elif amazon_manage in ["seach_albums", "seach_playlists", "seach_tracks", "seach_artists","seach_stations"]:  # 搜索
        data = seachAmazon(parameterDic, isRefresh, cacheTime, isL2Cache, background_tasks)
        # print(data)
        return data

    elif amazon_manage == "common":  # 执行url
        url = parameterDic.get('url')
        if not url:
            return {'vit_status': 2, 'vit_message': '201'}
        data = requestAirable(url, isRefresh=isRefresh, cacheTime=cacheTime, isL2Cache=isL2Cache, background_tasks=background_tasks)
        return data

    # ------------------------------------------------登录状态/登出------------------------------------------------------
    elif amazon_manage == "initAmazon":  # 用户登录后，调用该接口
        setAmazonLoginStatus(True)
        print('initAmazon')
        background_tasks.add_task(initAmazon)
        return {'vit_status': 0, 'vit_message': ''}

    # ------------------------------------------------登录状态/登出------------------------------------------------------
    elif amazon_manage == 'logout':
        return amazon_logout()
    # -----------------------------------------------播放-------------------------------------------------------------------
    elif amazon_manage == 'track_url':    # 弃用
        url = getPlayUrl(parameterDic, background_tasks)
        return url

    elif amazon_manage == 'add_track':  # 添加到播放队列
        res = amazon_add_track(parameterDic,background_tasks)
        return res

    elif amazon_manage == 'play_album':  # 播放整张专辑
        track_url = parameterDic.get('track_url')
        playlist_url = parameterDic.get('album_url')
        res = playListOrAlbum(playlist_url, 'w+', track_url, background_tasks)
        return res

    elif amazon_manage == 'play_playlist':  # 播放列表 从这里开始播放
        track_url = parameterDic.get('track_url')
        playlist_url = parameterDic.get('playlist_url')
        res = playListOrAlbum(playlist_url, 'w+', track_url, background_tasks)
        return res

    elif amazon_manage == 'play_my_track':  # 播放收藏的曲目
        playlist_url = allAmazonOrder.get('my_tracks')
        track_url = parameterDic.get('track_url')
        res = playListOrAlbum(playlist_url, 'w+', track_url, background_tasks)
        return res

    elif amazon_manage == 'playlist_add_album':  # 将专辑添加到播放队列
        playlist_url = parameterDic.get('album_url')
        res = playListOrAlbum(playlist_url, 'a+', None, background_tasks)
        return res

    elif amazon_manage == 'playlist_add_playlist':  # 将播放列表添加到播放队列
        playlist_url = parameterDic.get('playlist_url')
        res = playListOrAlbum(playlist_url, 'a+', None, background_tasks)
        return res

    elif amazon_manage == 'play_artist_track':  # 艺术家->曲目->从这里开始播放

        track_url = parameterDic.get('track_url')
        playlist_url = parameterDic.get('url')
        res = playListOrAlbum(playlist_url, 'w+', track_url, background_tasks, pageLimit=True)
        return res

    elif amazon_manage == 'play_new_tracks':  # 播放首页的曲目
        playlist_url = allAmazonOrder.get('new_track')
        track_url = parameterDic.get('track_url')
        res = playListOrAlbum(playlist_url, 'w+', track_url, background_tasks)
        return res
    elif amazon_manage == 'play_track_for_you':    # 改成默认，不使用app传url的参数
        track_url = parameterDic.get('track_url')
        playlist_url = allAmazonOrder.get('track_for_you')
        res = playListOrAlbum(playlist_url, 'w+', track_url, background_tasks)
        return res

    elif amazon_manage == 'play_top_tracks':  # 曲风 - > 曲目
        track_url = parameterDic.get('track_url')
        playlist_url = allAmazonOrder.get('top_tracks')  # 改成默认，不使用app传url的参数
        res = playListOrAlbum(playlist_url, 'w+', track_url, background_tasks)
        return res
    elif amazon_manage == 'play_station':
        return amazon_play_station(parameterDic)

    elif amazon_manage == 'get_play_station_url':  # 播放电台url
        os.system(f'mpc crop > /dev/null 2>&1')
        play_url,prev_url,next_url=amazon_get_station_play_url(parameterDic)
        print(play_url)
        if prev_url:
            prev_track_url = f"{station_prefix}{prev_url}\n"
            os.system(f'mpc add {prev_track_url} > /dev/null 2>&1')
            os.system(f'mpc move 2 1 > /dev/null 2>&1')
        if next_url:
            next_track_url = f"{station_prefix}{next_url}\n"
            os.system(f'mpc add {next_track_url} > /dev/null 2>&1')
    else:
        return {"vit_status": 98, "vit_message": "987"}


@router.get("/python/amazon/track_url", tags=["amazon"], response_class=HTMLResponse,include_in_schema=False)
def track_url(request: Request):  # async
    """
    通过曲目id路径返回播放的url
    """
    track_id = request.query_params.get('track_id')
    url = getPlayUrl(track_id)
    #TODO 非付费用户，没有streams，需要判断，tidal相同
    return url


@router.get("/amazon", tags=["amazon"], summary='播放链接')  # test
def proxy_api(url:str):  # async
    """
    播放器直接播放url，重定向返回播放地址
    """
    playUrl = getPlayUrl(url)
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
