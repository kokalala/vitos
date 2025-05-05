# -*- coding: utf-8 -*-
import json
import threading
import time

from fastapi import APIRouter, Request, BackgroundTasks
from qobuz.qobuzFun import *
from fastapi.responses import HTMLResponse
import binascii
import hashlib
from itertools import cycle
from starlette.responses import RedirectResponse

router = APIRouter()
appid = '950096963'

# ############################### tidal ###########################################################

qobuzhomepage_thread = threading.Thread(target=getQobuzHomepage)  # qobuz页面缓存线程： 获取qobuz每个页面
qobuzhomepage_thread.daemon = True
qobuzhomepage_thread.start()
# print(qobuzhomepage_thread)
# #
qobuz_cache_thread = threading.Thread(target=cacheQobuzQueue)  # qobuz缓存队列线程
qobuz_cache_thread.daemon = True
qobuz_cache_thread.start()


from fastapi import Query
from fastapi import Path as fastapiPath
from pydantic import BaseModel


# @router.get("/python/qobuz/initQobuz", tags=["qobuz"], summary='初始化请求', description='qobuz登录后请求该接口，获取首页缓存')
# def initQobuz(background_tasks: BackgroundTasks, app_os: str = 'android', app_v: int = 1):  # async
#     global isQobuzLogin
#     isQobuzLogin = True
#
#     #background_tasks.add_task(initQobuzFun)
#     return request.headers#{"vit_status": 0, "vit_message": ""}


@router.get("/python/qobuz/user_login", tags=["qobuz"], summary='登录')
def user_login(
        background_tasks: BackgroundTasks,
        username: str = Query(..., description="qobuz用户名"),
        password: str = Query(..., description="qobuz密码"),
        app_os: str = 'android',
        app_v: int = 1):  # async
    """
    用户登录
    """
    parameters = {'username': username, 'password': password}
    data =td_qobuz_user_login(parameters)
    if data.get('vit_status') == 0:
        setQobuzLoginStatus(True)
        background_tasks.add_task(initQobuzFun)
    return data

@router.get("/python/qobuz/user_re_login", tags=["qobuz"], summary='重新登录')
def user_re_login(
        background_tasks: BackgroundTasks,
        # username: str = Query(..., description="qobuz用户名"),
        # password: str = Query(..., description="qobuz密码"),
        app_os: str = 'android',
        app_v: int = 1):  # async
    """
    用户登录
    """
    #parameters = {'username': username, 'password': password}
    #data = td_qobuz_user_login(parameters)
    data = td_qobuz_relogin()
    if data.get('vit_status') == 0:
        setQobuzLoginStatus(True)
        background_tasks.add_task(initQobuzFun)
    return data

@router.get("/python/qobuz/user_logout", tags=["qobuz"], summary='登出')
def user_logout(app_os: str = 'android', app_v: int = 1):  # async
    """
    用户退出qobuz帐号
    """
    return td_qobuz_Logout()


@router.get("/python/qobuz/maybe_login", tags=["qobuz"], summary='查询是否登录')
def maybe_login(app_os: str = 'android', app_v: int = 1):  # async
    """
    查询是否登录
    """
    return td_qobuz_maybe_login()


@router.get("/python/qobuz/index", tags=["qobuz-index"], summary='首页')
def index(
        background_tasks: BackgroundTasks,
        genre_ids: str = Query(None, description="默认：null,多个流派id，使用','逗号隔开"),
        isRefresh: int = Query(0, description="0：不强制刷；1：强制刷新"),
        cacheTime: int = Query(cacheDefaultTime, description="缓存时间"),
        isL2Cache: int = Query(9, description="二级缓存:: -1：不执行，0~30：执行缓存数量，99：全部执行"),
        app_os: str = 'android',
        app_v: int = 1):  # async

    """
    首页
    """
    parametrOther = {'isRefresh': isRefresh, 'cacheTime': cacheTime, 'isL2Cache': isL2Cache, 'background_tasks': background_tasks}

    ids = resetGenreIDs(genre_ids)
    parameter = {**ids}
    path = os.path.join(cacheQobuzDir, allQobuzOrder['index']['path'].format(**parameter))
    data = requestQobuz(allQobuzOrder['index']['url'], parameter, path, **parametrOther)
    genreIdsJson = readFile(qobuzGenreIds)
    if app_os == 'android':
        genreIdsJson['android'] = ids
    elif app_os == 'ios':
        genreIdsJson['ios'] = ids
    writeCacheFile(qobuzGenreIds, genreIdsJson)
    return data


@router.get("/python/qobuz/featured_albums", tags=["qobuz-index"], summary='新发行')
def featured_albums(
        background_tasks: BackgroundTasks,
        genre_ids: str = Query(None, description="默认：null,多个流派id，使用','逗号隔开"),
        isRefresh: int = Query(0, description="0：不强制刷；1：强制刷新"),
        cacheTime: int = Query(cacheDefaultTime, description="缓存时间"),
        isL2Cache: int = Query(9, description="二级缓存:: -1：不执行，0~30：执行缓存数量，99：全部执行"),
        app_os: str = 'android',
        app_v: int = 1):  # async

    """
    获取推荐专辑
    """
    parametrOther = {'isRefresh': isRefresh, 'cacheTime': cacheTime, 'isL2Cache': isL2Cache, 'background_tasks': background_tasks}
    ids = resetGenreIDs(genre_ids)
    parameter = {**ids}
    path = os.path.join(cacheQobuzDir, allQobuzOrder['featured_albums']['path'].format(**parameter))
    data = requestQobuz(allQobuzOrder['featured_albums']['url'], parameter, path, **parametrOther)
    # print(json.dumps(data))
    return data  # td_qobuz_api_request(parameterDic, '/featured/albums')


@router.get("/python/qobuz/album_getfeatured", tags=["qobuz-index"], summary='发现/新发行/(全部、流行中、媒体好评、热门发行)，发现/Qobuz风格/(Qobuz全集、理想音乐作品)')
def album_getfeatured(
        background_tasks: BackgroundTasks,
        genre_ids: str = Query(None, description="默认：null,多个流派id，使用','逗号隔开"),
        type: str = Query(..., description="new-releases-full: 全部,<br/>recent-releases: 流行中,<br/>press-awards: 媒体好评,<br/>most-streamed: 热门发行，<br/>qobuzissims: Qobuz全集,<br/>ideal-discography: 理想音乐作品集"),
        offset: int = 0,
        limit: int = 30,
        isRefresh: int = Query(0, description="0：不强制刷；1：强制刷新"),
        cacheTime: int = Query(cacheDefaultTime, description="缓存时间"),
        isL2Cache: int = Query(99, description="二级缓存:: -1：不执行，0~30：执行缓存数量，99：全部执行"),
        app_os: str = 'android',
        app_v: int = 1):  # async
    """
    获取推荐专辑\n
    type全部类型:\n
        most-streamed, best-sellers, new-releases, press-awards,editor-picks, most-featured, new-releases-full, recent-releases,ideal-discography, qobuzissims, album-of-the-week,re-release-of-the-week
    """
    parametrOther = {'isRefresh': isRefresh, 'cacheTime': cacheTime, 'isL2Cache': isL2Cache, 'background_tasks': background_tasks}
    if isRefresh == 1:  # 如果是强制刷新，清除第二页以下的缓存
        delPath = os.path.join(cacheQobuzDir, f"index/album_getfeatured/{type}_genres_ids={genre_ids}*")
        delCacheFile(delPath)
    ids = resetGenreIDs(genre_ids)
    parameter = {'offset': offset, 'limit': limit, 'type': type, **ids}
    path = os.path.join(cacheQobuzDir, allQobuzOrder['album_getfeatured']['path'].format(**parameter))
    data = requestQobuz(allQobuzOrder['album_getfeatured']['url'], parameter, path, **parametrOther)
    return data


@router.get("/python/qobuz/album_detail", tags=["qobuz-index"], summary='专辑详情')
def album_detail(
        background_tasks: BackgroundTasks,
        album_id: str = Query(..., description="专辑id"),
        isRefresh: int = Query(0, description="0：不强制刷；1：强制刷新"),
        cacheTime: int = Query(cacheDefaultTime, description="缓存时间"),
        isL2Cache: int = Query(-1, description="二级缓存:: -1：不执行，0~30：执行缓存数量，99：全部执行"),
        app_os: str = 'android',
        app_v: int = 1):  # async
    """
    专辑详情
    """
    parametrOther = {'isRefresh': isRefresh, 'cacheTime': cacheTime, 'isL2Cache': isL2Cache, 'background_tasks': background_tasks}
    parameter = {'album_id': album_id}
    path = os.path.join(cacheQobuzDir, allQobuzOrder['album_detail']['path'].format(**parameter))
    data = requestQobuz(allQobuzOrder['album_detail']['url'], parameter, path, **parametrOther)
    return data


@router.get("/python/qobuz/artist_detail", tags=["qobuz-index"], summary='艺术家详情')
def artist_detail(
        background_tasks: BackgroundTasks,
        artist_id: str = Query(..., description="艺术家id"),
        offset: int = Query(0, description="偏移数"),
        limit: int = Query(30, description="每页数量"),
        extra: str = Query('albums', description="默认:albums"),
        isRefresh: int = Query(0, description="0：不强制刷；1：强制刷新"),
        cacheTime: int = Query(cacheDefaultTime, description="缓存时间"),
        isL2Cache: int = Query(99, description="二级缓存:: -1：不执行，0~30：执行缓存数量，99：全部执行"),
        app_os: str = 'android',
        app_v: int = 1):  # async
    """
    艺术家详情
    """
    parametrOther = {'isRefresh': isRefresh, 'cacheTime': cacheTime, 'isL2Cache': isL2Cache, 'background_tasks': background_tasks}
    parameter = {'artist_id': artist_id, 'offset': offset, 'limit': limit, 'extra': extra}
    # print(parameter)
    path = os.path.join(cacheQobuzDir, allQobuzOrder['artist_detail']['path'].format(**parameter))
    data = requestQobuz(allQobuzOrder['artist_detail']['url'], parameter, path, **parametrOther)
    return data


@router.get("/python/qobuz/qobuz_playlists", tags=["qobuz-playlists"], summary='发现/Qobuz歌单')
def qobuz_playlists(
        background_tasks: BackgroundTasks,
        genre_ids: str = Query(None, description="默认：null,多个流派id，使用','逗号隔开"),
        offset: int = Query(0, description="偏移数"),
        limit: int = Query(500, description="每页数量"),
        type: str = Query('editor-picks', description="默认:editor-picks"),
        isRefresh: int = Query(0, description="0：不强制刷；1：强制刷新"),
        cacheTime: int = Query(cacheDefaultTime, description="缓存时间"),
        isL2Cache: int = Query(99, description="二级缓存:: -1：不执行，0~30：执行缓存数量，99：全部执行"),
        app_os: str = 'android',
        app_v: int = 1):  # async
    """
    发现/Qobuz歌单\n
    type 全部类型:\n
        last-created, editor-picks
    """
    if isRefresh == 1:  # 如果是强制刷新，清除第二页以下的缓存
        delPath = os.path.join(cacheQobuzDir, f"index/qobuz_playlists/{type}_genres_ids={genre_ids}*")
        delCacheFile(delPath)
    parametrOther = {'isRefresh': isRefresh, 'cacheTime': cacheTime, 'isL2Cache': isL2Cache, 'background_tasks': background_tasks}
    ids = resetGenreIDs(genre_ids)
    parameter = {'offset': offset, 'limit': limit, 'type': type, **ids}
    path = os.path.join(cacheQobuzDir, allQobuzOrder['qobuz_playlists']['path'].format(**parameter))
    data = requestQobuz(allQobuzOrder['qobuz_playlists']['url'], parameter, path, **parametrOther)
    return data  # td_qobuz_api_request(parameterDic, '/playlist/getFeatured')


@router.get("/python/qobuz/playlist_detail", tags=["qobuz-playlists"], summary='播放列表详情')
def playlist_detail(
        background_tasks: BackgroundTasks,
        playlist_id: str = Query(..., description="播放列表id"),
        offset: int = Query(0, description="偏移数"),
        limit: int = Query(500, description="每页数量"),
        extra: str = Query('tracks', description="默认:tracks"),
        isRefresh: int = Query(0, description="0：不强制刷；1：强制刷新"),
        cacheTime: int = Query(cacheDefaultTime, description="缓存时间"),
        isL2Cache: int = Query(-1, description="二级缓存:: -1：不执行，0~30：执行缓存数量，99：全部执行"),
        app_os: str = 'android',
        app_v: int = 1):  # async
    """
    发现/Qobuz歌单\n
    extra 全部类型:\n
        tracks, subscribers, getSimilarPlaylists, focus, focusAll
    """
    #  extra (accepted values are tracks, subscribers, getSimilarPlaylists, focus, focusAll)
    parametrOther = {'isRefresh': isRefresh, 'cacheTime': cacheTime, 'isL2Cache': isL2Cache, 'background_tasks': background_tasks}
    parameter = {'playlist_id': playlist_id, 'extra': extra, 'offset': offset, 'limit': limit}
    path = os.path.join(cacheQobuzDir, allQobuzOrder['playlist_detail']['path'].format(**parameter))
    data = requestQobuz(allQobuzOrder['playlist_detail']['url'], parameter, path, **parametrOther)
    # print(data)
    return data


@router.get("/python/qobuz/playlist_subscribe", tags=["qobuz-playlists"], summary='添加到我的收藏')
def playlist_subscribe(
        background_tasks: BackgroundTasks,
        playlist_id: str = Query(..., description="艺术家id"),
        isRefresh: int = Query(1, description="0：后台执行；1：强制刷新"),
        app_os: str = 'android',
        app_v: int = 1):  # async
    """
    将播放列表添加到 《我的播放列表》
    """
    parameter = {'playlist_id': playlist_id}
    data = actionPlaylist(parameter, '/playlist/subscribe', isRefresh, background_tasks)
    return data


@router.get("/python/qobuz/playlist_unsubscribe", tags=["qobuz-playlists"], summary='从我的收藏移除')
def playlist_unsubscribe(
        background_tasks: BackgroundTasks,
        playlist_id: str = Query(..., description="艺术家id"),
        isRefresh: int = Query(1, description="0：后台执行；1：强制刷新"),
        app_os: str = 'android',
        app_v: int = 1):  # async
    """
    将播放列表从 《我的播放列表》移除
    """
    parameter = {'playlist_id': playlist_id}
    data = actionPlaylist(parameter, '/playlist/unsubscribe', isRefresh, background_tasks)
    return data


@router.get("/python/qobuz/get_user_playlists", tags=["qobuz-playlists"], summary='我的播放列表')
def get_user_playlists(
        background_tasks: BackgroundTasks,
        offset: int = Query(0, description="偏移数"),
        limit: int = Query(30, description="每页数量"),
        isRefresh: int = Query(0, description="0：不强制刷；1：强制刷新"),
        cacheTime: int = Query(cacheDefaultTime, description="缓存时间"),
        isL2Cache: int = Query(-1, description="二级缓存:: -1：不执行，0~30：执行缓存数量，99：全部执行"),
        app_os: str = 'android',
        app_v: int = 1):  # async
    """
    获取用户的播放列表\n
        filter:(该参数没有使用)\n
            None：全部
            subscribe:订阅
            owner：用户创建
    """
    if isRefresh == 1:  # 如果是强制刷新，清除第二页以下的缓存
        delPath = os.path.join(cacheQobuzDir, f"index/getUserPlaylists*")
        delCacheFile(delPath)
    parametrOther = {'isRefresh': isRefresh, 'cacheTime': cacheTime, 'isL2Cache': isL2Cache, 'background_tasks': background_tasks, 'userFlag': True}
    parameter = {'offset': offset, 'limit': limit}
    path = os.path.join(cacheQobuzDir, allQobuzOrder['get_user_playlists']['path'].format(**parameter))
    data = requestQobuz(allQobuzOrder['get_user_playlists']['url'], parameter, path, **parametrOther)
    return data


@router.get("/python/qobuz/user_playlist_create", tags=["qobuz-playlists"], summary='用户创建的播放列表')
def user_playlist_create(
        name: str = Query(..., description="列表名称"),
        description: str = Query('', description="描述"),
        is_public: int = Query(0, description="是否具有协作性"),
        is_collaborative: int = Query(0, description="是否公开"),
        isRefresh: int = Query(1, description="0：后台执行；1：强制刷新"),
        app_os: str = 'android',
        app_v: int = 1):  # async
    """
    用户创建的播放列表\n
        name: str
            Name for the new playlist
        description: str
            Description for the playlist
        is_public: bool
            Flag to make the playlist public.
        is_collaborative: bool
            Flag to make the playlist collaborative.
    """
    parameter = {'name': name, 'description': description, 'is_public': is_public, 'is_collaborative': is_collaborative}
    delCacheFile(os.path.join(cacheQobuzDir, "index/getUserPlaylists*"))  # 删除缓存
    data = td_qobuz_api_request(parameter, '/playlist/create')
    print('用户创建的播放列表：', data.get('name'))
    time.sleep(1)  # 延时1秒，不然qobuz服务器没有反应过来，获取的还是旧的
    return data


@router.get("/python/qobuz/user_playlist_delete", tags=["qobuz-playlists"], summary=' 删除用户自己创建的播放列表')
def user_playlist_delete(
        background_tasks: BackgroundTasks,
        playlist_id: str = Query(..., description="列表id"),
        isRefresh: int = Query(1, description="0：后台执行；1：强制刷新"),
        app_os: str = 'android',
        app_v: int = 1):  # async
    """
    用户创建的播放列表
    """
    parameter = {'playlist_id': playlist_id}
    data = actionPlaylist(parameter, '/playlist/delete', isRefresh, background_tasks)
    # print('删除用户创建的播放列表：', data.get('status', 'fail'))
    return data


@router.get("/python/qobuz/user_playlist_update", tags=["qobuz-playlists"], summary=' 编辑播放列表的信息')
def user_playlist_update(
        background_tasks: BackgroundTasks,
        playlist_id: str = Query(..., description="列表id"),
        name: str = Query(..., description="列表名称"),
        description: str = Query('', description="描述"),
        is_public: int = Query(0, description="是否具有协作性"),
        is_collaborative: int = Query(0, description="是否公开"),
        isRefresh: int = Query(1, description="0：后台执行；1：强制刷新"),
        app_os: str = 'android',
        app_v: int = 1):  # async
    """
    编辑播放列表的信息
    """
    parameter = {'playlist_id': playlist_id, 'name': name, 'description': description, 'is_public': is_public, 'is_collaborative': is_collaborative}
    data = actionPlaylist(parameter, '/playlist/update', isRefresh, background_tasks)
    return data


@router.get("/python/qobuz/playlist_addtracks", tags=["qobuz-playlists"], summary=' 添加曲目到播放列表')
def playlist_addtracks(
        background_tasks: BackgroundTasks,
        playlist_id: str = Query(..., description="列表id"),
        track_ids: str = Query(..., description="曲目id"),
        isRefresh: int = Query(1, description="0：后台执行；1：强制刷新"),
        app_os: str = 'android',
        app_v: int = 1):  # async
    """
    添加曲目到播放列表
    """
    parameter = {'playlist_id': playlist_id, 'track_ids': track_ids}
    data = actionPlaylist(parameter, '/playlist/addTracks', isRefresh, background_tasks)
    return data


@router.get("/python/qobuz/playlist_deletetracks", tags=["qobuz-playlists"], summary=' 从当前播放列表中删除')
def playlist_deletetracks(
        background_tasks: BackgroundTasks,
        playlist_id: str = Query(..., description="播放列表id"),
        playlist_track_ids: str = Query(..., description="播放列表下面的曲目 playlist_track_ids"),
        isRefresh: int = Query(1, description="0：后台执行；1：强制刷新"),
        app_os: str = 'android',
        app_v: int = 1):  # async
    """
    从当前播放列表中删除
    """
    parameter = {'playlist_id': playlist_id, 'playlist_track_ids': playlist_track_ids}
    data = actionPlaylist(parameter, '/playlist/deleteTracks', isRefresh, background_tasks)
    return data


@router.get("/python/qobuz/favorite_ids", tags=["qobuz-favorite"], summary=' 收藏的所有ids')
def favorite_ids(
        background_tasks: BackgroundTasks,
        isRefresh: int = Query(0, description="0：不强制刷；1：强制刷新"),
        cacheTime: int = Query(cacheDefaultTime, description="缓存时间"),
        isL2Cache: int = Query(-1, description="二级缓存:: -1：不执行，0~30：执行缓存数量，99：全部执行"),
        app_os: str = 'android',
        app_v: int = 1):  # async
    """
    收藏的所有ids,包含专辑、曲目、艺术家
    """
    parameter = {}
    parametrOther = {'isRefresh': isRefresh, 'cacheTime': cacheTime, 'isL2Cache': isL2Cache, 'background_tasks': background_tasks,'userFlag':True}
    path = os.path.join(cacheQobuzDir, allQobuzOrder['favorite_ids']['path'].format(**parameter))
    data = requestQobuz(allQobuzOrder['favorite_ids']['url'], parameter, path, **parametrOther)
    return data


@router.get("/python/qobuz/favorite_create", tags=["qobuz-favorite"], summary=' 收藏添加')
def favorite_create(
        background_tasks: BackgroundTasks,
        album_ids: str = Query(None, description="专辑id"),
        track_ids: str = Query(None, description="曲目id"),
        artist_ids: str = Query(None, description="艺术家id"),
        isRefresh: int = Query(1, description="0：后台执行；1：强制刷新"),
        app_os: str = 'android',
        app_v: int = 1):  # async
    """
    收藏添加
    album_ids、track_ids、artist_ids只传入其中一个值，多个id用','隔开
    """
    parameter = {'album_ids': album_ids, 'track_ids': track_ids, 'artist_ids': artist_ids}
    data = actionFavorite(parameter, '/favorite/create', isRefresh, background_tasks)
    return data


@router.get("/python/qobuz/favorite_delete", tags=["qobuz-favorite"], summary=' 收藏移除')
def favorite_delete(
        background_tasks: BackgroundTasks,
        album_ids: str = Query(None, description="专辑id"),
        track_ids: str = Query(None, description="曲目id"),
        artist_ids: str = Query(None, description="艺术家id"),
        isRefresh: int = Query(1, description="0：后台执行；1：强制刷新"),
        app_os: str = 'android',
        app_v: int = 1):  # async
    """
    收藏移除
    album_ids、track_ids、artist_ids只传入其中一个值，多个id用','隔开
    """
    parameter = {'album_ids': album_ids, 'track_ids': track_ids, 'artist_ids': artist_ids}
    data = actionFavorite(parameter, '/favorite/delete', isRefresh, background_tasks)
    return data


@router.get("/python/qobuz/get_User_Favorites", tags=["qobuz-favorite"], summary='获取我的收藏')
def get_User_Favorites(
        background_tasks: BackgroundTasks,
        type: str = Query(None, description="默认：None,其他：'artists', 'albums' or 'tracks'"),
        offset: int = Query(0, description="偏移数"),
        limit: int = Query(50, description="每页数量"),
        isRefresh: int = Query(0, description="0：不强制刷；1：强制刷新"),
        cacheTime: int = Query(cacheDefaultTime, description="缓存时间"),
        isL2Cache: int = Query(99, description="二级缓存:: -1：不执行，0~30：执行缓存数量，99：全部执行"),
        app_os: str = 'android',
        app_v: int = 1):  # async
    """
    获取我的收藏
    type为空，获取所有的数据
    """
    if isRefresh == 1:  # 如果是强制刷新，清除第二页以下的缓存
        delPath = os.path.join(cacheQobuzDir, f"favorite/getUserFavorites_type={type}*")
        delCacheFile(delPath)
    parametrOther = {'isRefresh': isRefresh, 'cacheTime': cacheTime, 'isL2Cache': isL2Cache, 'background_tasks': background_tasks}
    parameter = {'type': type, 'offset': offset, 'limit': limit}
    path = os.path.join(cacheQobuzDir, allQobuzOrder['get_User_Favorites']['path'].format(**parameter))
    data = requestQobuz(allQobuzOrder['get_User_Favorites']['url'], parameter, path, **parametrOther)
    return data


@router.get("/python/qobuz/favorite_status", tags=["qobuz-favorite"], summary='收藏状态', include_in_schema=False)  # 弃用
def favorite_status(

        type: str = Query(..., description="'artist', 'album' or 'track'"),
        item: str = Query(..., description="对应的id"),
        app_os: str = 'android',
        app_v: int = 1):  # async
    """
    收藏状态
    """
    parameter = {'type': type, 'item': item}
    data = td_qobuz_api_request(parameter, 'favorite/status')
    return data


@router.get("/python/qobuz/{obj}_search", tags=["qobuz-search"], summary='搜索')
def search(
        background_tasks: BackgroundTasks,
        obj: str = fastapiPath('catalog', description="catalog、track、album、artist、playlist"),
        query: str = Query(..., description="搜索内容"),
        offset: int = Query(0, description="偏移数"),
        limit: int = Query(50, description="每页数量"),
        isRefresh: int = Query(0, description="0：不强制刷；1：强制刷新"),
        cacheTime: int = Query(cacheDefaultTime, description="缓存时间"),
        isL2Cache: int = Query(99, description="二级缓存:: -1：不执行，0~30：执行缓存数量，99：全部执行"),
        app_os: str = 'android',
        app_v: int = 1):  # async
    """
    搜索\n
    obj：\n
        catalog：搜索和返回所有类别值
        track：搜索曲目
        album：搜索专辑
        artist：搜索艺术家
        playlist:搜索歌单
    """
    parametrOther = {'isRefresh': isRefresh, 'cacheTime': cacheTime, 'isL2Cache': isL2Cache, 'background_tasks': background_tasks}
    parameter = {'offset': offset, 'limit': limit, 'query': query}
    path = os.path.join(cacheQobuzDir, allQobuzOrder[obj + '_search']['path'].format(**parameter))
    data = requestQobuz(allQobuzOrder[obj + '_search']['url'], parameter, path, **parametrOther)
    return data


@router.get("/python/qobuz/get_featured_types", tags=["qobuz-index"], summary='获取精选分类', include_in_schema=False)
def get_featured_types(
        request: Request,
        app_os: str = 'android',
        app_v: int = 1):  # async
    """
    返回分类列表，如 best-seller, new-releases, press-awards, most-streamed, editor-picks, most-featured
    """
    data = td_qobuz_api_request(request, '/catalog/getFeaturedTypes')
    return data


@router.get("/python/qobuz/get_featured", tags=["qobuz-index"], summary='获取精选目录', include_in_schema=False)
def get_featured(
        request: Request,
        app_os: str = 'android',
        app_v: int = 1):  # async
    """
    返回 艺术家、专辑、播放列表、文章
    """
    data = td_qobuz_api_request(request, '/catalog/getFeatured')
    return data


@router.get("/python/qobuz/add_track", tags=["qobuz-play"], summary='下一首播放；加到播放队列')
def add_track(
        track_id: str = Query(..., description="专辑id"),
        model: str = Query('insert', description="insert:下一首播放，add:添加到播放队列，play:立即播放"),
        Artist: str = Query(None, description="艺术家"),
        AlbumArtist: str = Query(None, description="专辑艺术家"),
        Title: str = Query(None, description="歌曲名称"),
        Track: str = Query(None, description="歌曲序号，1、2、3、、、trackNumber"),
        Genre: str = Query(None, description="流派"),
        Date: str = Query(None, description="发行时间 releaseDate"),
        Cover: str = Query(None, description="专辑封面"),
        CoverPreview=Query(None, description="专辑封面-小图"),
        Label: str = Query(None, description="标签 label"),
        Composer: str = Query(None, description="作曲家 composer"),
        Time: str = Query(None, description="歌曲时长 playtime"),
        duration: str = Query(None, description="歌曲时长 playtime"),
        Format: str = Query(None, description="歌曲频率 44.1、48、96、384、、format"),
        Album: str = Query(None, description="所属专辑"),

        app_os: str = 'android',
        app_v: int = 1):  # async
    """
    下一首播放
    """
    parameter = {'track_id': track_id, 'model': model, 'Artist': Artist, 'AlbumArtist': AlbumArtist, 'Title': Title, 'Track': Track, 'Genre': Genre, 'Date': Date, 'Cover': Cover,
                 'CoverPreview': CoverPreview, 'Label': Label, 'Composer': Composer, 'Cover': Cover, 'Time': Time, 'duration': duration, 'Format': Format, 'Album': Album}
    return qobuz_next_track(parameter)


@router.get("/python/qobuz/play_album", tags=["qobuz-play"], summary='播放专辑')
def play_album(
        background_tasks: BackgroundTasks,
        album_id: str = Query(..., description="专辑id"),
        track_id: int = Query(None, description="歌曲的id"),
        app_os: str = 'android',
        app_v: int = 1):  # async
    """
    播放专辑
    """
    qobuz_manage = 'album_detail'
    parameter = {'album_id': album_id}
    path = os.path.join(cacheQobuzDir, allQobuzOrder['album_detail']['path'].format(**parameter))
    reqData = requestQobuz(allQobuzOrder['album_detail']['url'], parameter, path)
    if reqData.get('vit_status') != 0:
        return reqData
    print(json.dumps(reqData))
    data = qobuz_play_album(reqData, track_id, isAlbum=True, playType='w+', qobuz_manage=qobuz_manage, parameter=parameter, background_tasks=background_tasks)
    return data


@router.get("/python/qobuz/play_playlist", tags=["qobuz-play"], summary='播放歌单')
def play_playlist(
        background_tasks: BackgroundTasks,
        playlist_id: str = Query(..., description="歌单id"),
        track_id: int = Query(None, description="歌曲的id"),
        app_os: str = 'android',
        app_v: int = 1):  # async
    """
    播放歌单
    """
    qobuz_manage = 'playlist_detail'
    parameter = {'playlist_id': playlist_id, 'extra': 'tracks', 'offset': 0, 'limit': 500}
    path = os.path.join(cacheQobuzDir, allQobuzOrder[qobuz_manage]['path'].format(**parameter))
    reqData = requestQobuz(allQobuzOrder[qobuz_manage]['url'], parameter, path)
    # print(json.dumps(reqData))
    data = qobuz_play_album(reqData, track_id, isAlbum=False, playType='w+', qobuz_manage=qobuz_manage, parameter=parameter, background_tasks=background_tasks)
    return data


@router.get("/python/qobuz/play_my_track", tags=["qobuz-play"], summary='播放我的歌曲')
def play_my_track(
        background_tasks: BackgroundTasks,
        track_id: int = Query(None, description="歌曲的id"),
        app_os: str = 'android',
        app_v: int = 1):  # async
    """
    播放我的歌曲
    """
    qobuz_manage = 'get_User_Favorites'
    parameter = {'type': 'tracks', 'offset': 0, 'limit': 50}
    path = os.path.join(cacheQobuzDir, allQobuzOrder[qobuz_manage]['path'].format(**parameter))
    reqData = requestQobuz(allQobuzOrder[qobuz_manage]['url'], parameter, path)
    data = qobuz_play_album(reqData, track_id, isAlbum=False, playType='w+', qobuz_manage=qobuz_manage, parameter=parameter, background_tasks=background_tasks)
    return data


@router.get("/python/qobuz/playlist_add_album", tags=["qobuz-play"], summary='添加专辑到播放队列')
def playlist_add_album(
        background_tasks: BackgroundTasks,
        album_id: str = Query(..., description="专辑id"),
        track_id: int = Query(None, description="歌曲的id"),
        app_os: str = 'android',
        app_v: int = 1):  # async
    """
    添加专辑到播放队列
    """
    qobuz_manage = 'album_detail'
    parameter = {'album_id': album_id, 'offset': 0, 'limit': 500}
    path = os.path.join(cacheQobuzDir, allQobuzOrder[qobuz_manage]['path'].format(**parameter))
    reqData = requestQobuz(allQobuzOrder[qobuz_manage]['url'], parameter, path)
    data = qobuz_play_album(reqData, track_id, isAlbum=True, playType='a+', qobuz_manage=qobuz_manage, parameter=parameter, background_tasks=background_tasks)
    return data


@router.get("/python/qobuz/playlist_add_playlist", tags=["qobuz-play"], summary='添加歌单到播放队列')
def playlist_add_playlist(
        background_tasks: BackgroundTasks,
        playlist_id: str = Query(..., description="歌单id"),
        track_id: int = Query(None, description="歌曲的id"),
        app_os: str = 'android',
        app_v: int = 1):  # async
    """
    添加歌单到播放队列
    """
    qobuz_manage = 'playlist_detail'
    parameter = {'playlist_id': playlist_id, 'extra': 'tracks', 'offset': 0, 'limit': 500}
    path = os.path.join(cacheQobuzDir, allQobuzOrder[qobuz_manage]['path'].format(**parameter))
    reqData = requestQobuz(allQobuzOrder[qobuz_manage]['url'], parameter, path)

    data = qobuz_play_album(reqData, track_id, isAlbum=False, playType='a+', qobuz_manage=qobuz_manage, background_tasks=background_tasks)
    return data


# @router.get("/python/qobuz/play_album", tags=["qobuz-play"], summary='播放专辑')
# def play_album(
#         album_id: str,
#         track_id: int = Query(None, description="搜索内容"),
#         app_os: str = 'android',
#         app_v: int = 1):  # async
#     """
#     下一首播放
#     """
#     qobuz_manage = 'album_detail'
#     parameter = {'album_id': album_id}
#     path = os.path.join(cacheQobuzDir, allQobuzOrder['album_detail']['path'].format(**parameter))
#     reqData = requestQobuz(allQobuzOrder['album_detail']['url'], parameter, path)
#     print(json.dumps(reqData))
#     # print(json.dumps(reqData))
#     data = qobuz_play_album(reqData, track_id, isAlbum=True, playType='w+', qobuz_manage=qobuz_manage, parameter=parameter, background_tasks=background_tasks)
#     return data

@router.get("/python/qobuz/all_genres", tags=["qobuz-index"], summary='获取所有的流派')
def all_genres(
        background_tasks: BackgroundTasks,
        isRefresh: int = Query(0, description="0：不强制刷；1：强制刷新"),
        cacheTime: int = Query(cacheDefaultTime, description="缓存时间"),
        isL2Cache: int = Query(-1, description="二级缓存:: -1：不执行，0~30：执行缓存数量，99：全部执行"),
        app_os: str = 'android',
        app_v: int = 1):  # async
    """
    获取所有的流派
    """
    parametrOther = {'isRefresh': isRefresh, 'cacheTime': cacheTime, 'isL2Cache': isL2Cache, 'background_tasks': background_tasks}
    path = os.path.join(cacheQobuzDir, allQobuzOrder['all_genres']['path'])
    data = requestQobuz(allQobuzOrder['all_genres']['url'], {}, path,**parametrOther)
    return data




@router.get("/python/qobuz/track_url", tags=["qobuz"], response_class=HTMLResponse, summary='获取曲目播放地址')
def track_url(track_id: int, format_id: int = 27, intent: str = 'stream'):  # async
    """
    track_id: int\n
        Track-ID to get the url for
    format_id: int\n
        Format ID following qobuz specifications:
         5: MP3 320
         6: FLAC Lossless
         7: FLAC Hi-Res 24 bit =< 96kHz,
        27: FLAC Hi-Res 24 bit >96 kHz & =< 192 kHz
    intent: str\n
        How the application will use the file URL
        Either 'stream', 'import', or 'download'.
    """
    # print(request.query_params)
    # track_id = request.query_params.get('track_id')
    # fmt_id = request.query_params.get('format_id')

    data = getTrachUrl(format_id, intent, track_id)
    # 时间错误{'vit_status': 4, 'vit_message': 'Expired request (request_ts) (Root=1-627a5338-28d0bc4e1a53b9e07024eb3c)'}
    if data.get('vit_status') == 4 and 'Expired request (request_ts)' in data.get('vit_message', ''):
        time.sleep(1)
        data = getTrachUrl(format_id, intent, track_id)
    if data.get('vit_status') == 0:
        url = data.get('url','')
    else:
        url = ""
    print('播放器获取的播放URL:', data)
    return url

@router.get("/python/clearQobuzCache", tags=["public api"], summary='清除qobuz所有缓存')
def clearQobuzCache(
        background_tasks: BackgroundTasks,
        platform:str = Query(..., description="清除缓存：'qobuz','amazon','tidal','all'"),
        app_os: str = 'android',
        app_v: int = 1):  # async
    """
    清除qobuz、amazon或tidal所有缓存
    """
    if platform in ['qobuz', 'amazon', 'tidal']:
        clearCache(platform)
    elif platform == 'all':
        clearCache('qobuz')
        clearCache('amazon')
        clearCache('tidal')

    return {'vit_status': 0, 'vit_mesage': ''}

@router.get("/qobuz/{track_id}", tags=["qobuz"])  # test
def proxy_api(track_id: int, format_id: int = 27, intent: str = 'stream'):  # async
    """
    track_id: int\n
        Track-ID to get the url for
    format_id: int\n
        Format ID following qobuz specifications:
         5: MP3 320
         6: FLAC Lossless
         7: FLAC Hi-Res 24 bit =< 96kHz,
        27: FLAC Hi-Res 24 bit >96 kHz & =< 192 kHz
    intent: str\n
        How the application will use the file URL
        Either 'stream', 'import', or 'download'.
    """
    # print(request.query_params)
    # track_id = request.query_params.get('track_id')
    # fmt_id = request.query_params.get('format_id')

    data = getTrachUrl(format_id, intent, track_id)
    # 时间错误{'vit_status': 4, 'vit_message': 'Expired request (request_ts) (Root=1-627a5338-28d0bc4e1a53b9e07024eb3c)'}
    if data.get('vit_status') == 4 and 'Expired request (request_ts)' in data.get('vit_message', ''):
        time.sleep(1)
        data = getTrachUrl(format_id, intent, track_id)
    if data.get('vit_status') == 0:
        url = data.get('url','')
    else:
        url = ""
    print('播放器获取的播放URL:', url)
    # url = getPlayUrl(track_id, quality=quality)
    response = RedirectResponse(url=url)
    return response



# @router.get("/test", tags=["test"])  # test
# def test():  # async
#
#     # print(request.query_params)
#     # track_id = request.query_params.get('track_id')
#     # fmt_id = request.query_params.get('format_id')
#     a=1/0
#     response = {}
#     return response