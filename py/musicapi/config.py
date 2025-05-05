import sys
site_packages = '/srv/py/musicapi/static/site-packages'
sys.path.append(site_packages)
import requests, urllib3, base64, uuid, random, string
import os
import sys
import json
from urllib.parse import unquote, urlencode, quote
import time
from concurrent.futures import ThreadPoolExecutor
import math
from subprocess import Popen, PIPE
import re
import subprocess, random
from pathlib import Path
import socket, cgi
import threading
from starlette.responses import RedirectResponse
from loguru import logger
desc = """
Qobuz说明\r\n
1、请求连接失败：{"vit_status":4,"vit_message":"444"}\r\n
2、服务器错误：{"vit_status":4,"vit_message":响应状态码如：401、400等}\r\n
3、获取到的数据不是json：{"vit_status":4,"vit_message":'446'}\r\n
4、返回的数据存在错误的信息：{"vit_status": 4, "vit_message": '447'}\r\n
5、如果是请求正常会将"vit_status": 0, "vit_message": ''添加在响应的json数据中，详细的使用请查看Qobuz接口文档。\r\n
6、缺少必需参数{"vit_status":2,'vit_message':”201”,”202”.............}vit_message的尾数是缺少的参数的位置。\r\n
7、用户没有登录{"vit_status": 1, "vit_message": '101'}\r\n
8、数据或服务器错误，详情查看vit_message信息，{"vit_status": 5, "vit_message": '101'}\r\n
"""
debug = False
serverIP = "127.0.0.1"
FastapiInfo = {
    'title':"在线音乐Api",
    'description':desc,
    # 'docs_url':'/python/docs',
    # 'redoc_url':'/python/redoc',
    'openapi_url':'/python/openapi.json',
}
pathLogger = "/mnt/streaming_cache/logs"  # 日志地址
app_song_info = '/mnt/mpd/app_song_info'  # mpd歌曲信息文件
tidal_m3u8_path = "/tmp/vitos_tidal_list.m3u8" # tidal添加歌曲到播放器的临时文件
amazon_m3u8_path = "/tmp/vitos_amazon_list.m3u8"  # amazon添加歌曲到播放器的临时文件
quality_info = '/mnt/settings/tidal_streaming_quality.conf'  # tidal保存音质参数的文件
cacheMainDir = "/mnt/streaming_cache"  # 缓存的临时文件夹
staticDir = '/srv/py/musicapi/'  # 静态文件夹的主路径
airable_request = 'airable {}'
COMMAND_MPC = 'mpc'  # mpc的执行文件
global passwordStr  # 在第三方网站获取airable的访问密码
passwordStr = None
global passwordExpires  # 密码的时效
passwordExpires = time.time()
sessionJson = "/mnt/streaming_cache/session.json"  # airable token信息
if not os.path.exists(os.path.dirname(sessionJson)):
    os.makedirs(os.path.dirname(sessionJson))
requests.adapters.DEFAULT_RERIES = 50  # request参数
urllib3.disable_warnings()
airableHost = "https://meta.airable.io/"  # airable访问地址
cacheDefaultTime = 60 * 60 * 48  # 默认缓存时间
cacheQueueCount = 2  # 缓存队列 弃用
global appVisitTime  # app最近访问时间
appVisitTime = time.time()
cacheListLimit = 1000  # 队列限制
cacheTimeout = 24 * 60 * 60  # 线程缓存失效时间
uid = "a6ecd6f4-00f3-11ec-b143-1f4b2d371131"  # airable 的uid

# ##################################################################################################################################################
# #######################################################tidal######################################################################################
# ##################################################################################################################################################
vit_prefix_tidal = "http://online.silentangel.audio/tidal?url="
cacheTidalDir = "/mnt/streaming_cache/tidal/"  # 缓存文件地址
global cacheTidalList
cacheTidalList = []  # 缓存队列：针对首页缓存 和 二级缓存
global asyncCacheTidalList
asyncCacheTidalList = []  # 异步缓存队列：针对已经有缓存的页面，再次访问，先拿到缓存后，再后台刷新当前缓存数据
global tidalPlayFlag  # 播放标记，防止列表刷新后，失效的后台数据插入
tidalPlayFlag = time.time()
global isTidalLogin
isTidalLogin = True  # 是否登录

allTidalOrder = {
    # "index": "https://meta.airable.io/tidal",  # 首页
    # ---------------------------------------------------new-----------------------------------------------------------
    "new_playlist": "https://meta.airable.io/tidal/new/playlists?p=1",  # 首页-最新-最新播放列表
    "new_album": "https://meta.airable.io/tidal/new/albums?p=1",  # 首页-最新-最新专辑
    "new_track": "https://meta.airable.io/tidal/new/tracks?p=1",  # 首页-最新-新歌
    # ---------------------------------------------------TIDAL Rising--------------------------------------------------
    "rising_album": "https://meta.airable.io/tidal/rising/albums?p=1",  # 首页-上升榜-专辑
    "rising_track": "https://meta.airable.io/tidal/rising/tracks?p=1",  # 首页-上升榜-曲目
    # ------------------------------------------------- TIDAL Masters----------------------------------------
    "master_album": "https://meta.airable.io/tidal/master/albums",  # 首页-母带-播放列表
    "master_playlist": "https://meta.airable.io/tidal/master/playlists",  # 首页-母带-专辑
    # ------------------------------------------------- Playlists-------------------------------------------
    "by_mood": "https://meta.airable.io/tidal/playlists/moods",  # 首页-播放列表-心情选单
    "playlist_new": "https://meta.airable.io/tidal/playlists/new",  # 首页-播放列表-最新播放列表
    "recommended_playlist": "https://meta.airable.io/tidal/playlists/recommended",  # 首页-播放列表-推荐播放列表

    # ------------------------------------------------ My Music--------------------------------------------------------
    "my_playlists": "https://meta.airable.io/tidal/my/playlists?s=a-z",  # 首页-我的收藏-专辑
    "my_albums": "https://meta.airable.io/tidal/my/albums?s=a-z",  # 首页-我的收藏-播放列表
    "my_tracks": "https://meta.airable.io/tidal/my/tracks?p=1&s=a-z",  # 首页-我的收藏-曲目
    "my_artists": "https://meta.airable.io/tidal/my/artists?s=a-z",  # 首页-我的收藏-艺术家
    # ------------------------------------------------ Genres ----------------------------------------------------------
    "genres": "https://meta.airable.io/tidal/genres",  # 首页-曲风
    # "insert_new_playlist": "https://meta.airable.io/actions/tidal/track/{track_id}/playlist/new/insert?name={playlist_name}",
    # "insert_playlist": "https://meta.airable.io/actions/tidal/track/{track_id}/playlist/{id}/insert",
    # "seach_albums": "https://meta.airable.io/tidal/search/albums?q={query}",
    # "seach_playlists": "https://meta.airable.io/tidal/search/playlists?q={query}",
    # "seach_tracks": "https://meta.airable.io/tidal/search/tracks?q={query}",
    # "seach_artists": "https://meta.airable.io/tidal/search/artists?q={query}",

    "common": "",  # 访问参数里面带有url
    "quality_set": "",  # 播放音质
    "login_and_quality": "",  # 查询是否登录
    "logout": "",
    "track_url": "",
    "add_track": "",
    "play_album": "",
    "play_playlist": "",
    "play_my_track": "",
    "playlist_add_album": "",
    "playlist_add_playlist": "",
    "play_seach_track": "",
    "add_seach_track": "",
    "play_artist_track": "",
    "add_artist_track": "",
    "play_new_tracks": "",  # "\"https://meta.airable.io/tidal/new/tracks?p={}\"",
    "play_rising_tracks": "",  # "https://meta.airable.io/tidal/rising/tracks?p={}",
    "play_top_tracks": "",

}


# ##################################################################################################################################################
# #######################################################amazon######################################################################################
# ##################################################################################################################################################
vit_prefix_amazon = "http://online.silentangel.audio/amazon?url="  # 保存歌曲的路径
station_prefix='http://online.silentangel.audio/amazon/station?url='  # 保存歌曲的路径
cacheAmazonDir = "/mnt/streaming_cache/amazon/"  # 缓存文件地址
global amazonPlayFlag  # 播放标记，防止列表刷新后，失效的后台数据插入
amazonPlayFlag = time.time()
global cacheAmazonList
cacheAmazonList = []  # 缓存队列：针对首页缓存 和 二级缓存
global asyncCacheAmazonList
asyncCacheAmazonList = []  # 异步缓存队列：针对已经有缓存的页面，再次访问，先拿到缓存后，再后台刷新当前缓存数据

global isAmazonLogin
isAmazonLogin = True
allAmazonOrder = {
    #"index": "https://meta.airable.io/amazon",  # 首页
    # --------------------------------------------------------------------------2.new-------------------------------------------------------------------------------
    "new_playlist": "https://meta.airable.io/amazon/document/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2NhdGFsb2dcL25ld1wvcGxheWxpc3RzXC8jbmV3X3BsYXlsaXN0c19kZXNjIl0",  #
    "new_album": "https://meta.airable.io/amazon/document/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2NhdGFsb2dcL25ld1wvYWxidW1zXC8jbmV3X2FsYnVtc19kZXNjIl0",  #
    "new_track": "https://meta.airable.io/amazon/playlist/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2NhdGFsb2dcL25ld1wvdHJhY2tzXC8jbmV3X3RyYWNrc19kZXNjIl0",  #
    # ---------------------------------------------------------------------------3.playlist------------------------------------------------------------------------
    "all_playlist": "https://meta.airable.io/amazon/document/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2NhdGFsb2dcL25ld1wvcGxheWxpc3RzXC8jbmV3X3BsYXlsaXN0c19kZXNjIl0",  #
    "recently_played": "https://meta.airable.io/amazon/document/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2NhdGFsb2dcL3BsYXlsaXN0c1wvcmVjZW50XC8jcmVjZW50bHlfcGxheWVkX3BsYXlsaXN0cyJd",  #
    "genres": "https://meta.airable.io/amazon/document/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2NhdGFsb2dcL3BsYXlsaXN0c1wvI3JlZmluZV9nZW5yZXMiXQ",  #
    "moods_activities": "https://meta.airable.io/amazon/document/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2NhdGFsb2dcL3BsYXlsaXN0c1wvI3JlZmluZV9tb29kc19hbmRfYWN0aXZpdGllcyJd",  #
    # ----------------------------------------------------------------------------4.Recommended---------------------------------------------------------------------
    "playlist_for_you": "https://meta.airable.io/amazon/document/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2NhdGFsb2dcL3JlY3NcL3BsYXlsaXN0c1wvI3JlY3NfcGxheWxpc3RzX2Rlc2MiXQ",  #
    "album_for_you": "https://meta.airable.io/amazon/document/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2NhdGFsb2dcL3JlY3NcL2FsYnVtc1wvI3JlY3NfYWxidW1zX2Rlc2MiXQ",  #
    "track_for_you": "https://meta.airable.io/amazon/playlist/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2NhdGFsb2dcL3JlY3NcL3RyYWNrc1wvI3JlY3NfdHJhY2tzX2Rlc2MiXQ",  #
    "station_for_you": "https://meta.airable.io/amazon/document/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2NhdGFsb2dcL3JlY3NcL3N0YXRpb25zXC8jcmVjc19zdGF0aW9uc19kZXNjIl0",  #
    # ------------------------------------------------------------------------------6.Charts------------------------------------------------------------------------
    "top_playlists": "https://meta.airable.io/amazon/document/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2NhdGFsb2dcL3BvcHVsYXJcL3BsYXlsaXN0c1wvI3BvcHVsYXJfcGxheWxpc3RzX2Rlc2MiXQ",  #
    "top_albums": "https://meta.airable.io/amazon/document/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2NhdGFsb2dcL3BvcHVsYXJcL2FsYnVtc1wvI3BvcHVsYXJfYWxidW1zX2Rlc2MiXQ",  #
    "top_tracks": "https://meta.airable.io/amazon/playlist/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2NhdGFsb2dcL3BvcHVsYXJcL3RyYWNrc1wvI3BvcHVsYXJfdHJhY2tzX2Rlc2MiXQ",  #
    "top_stations": "https://meta.airable.io/amazon/document/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2NhdGFsb2dcL3BvcHVsYXJcL3N0YXRpb25zXC8jcG9wdWxhcl9zdGF0aW9uc19kZXNjIl0",  #
    # --------------------------------------------------------------------------------------------------7.My Music-----------------------------------------------------
    "my_playlists": "https://meta.airable.io/amazon/document/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2xpYnJhcnlcL3BsYXlsaXN0c1wvI2xpYnJhcnlfcGxheWxpc3RzIl0",  #
    "my_artists": "https://meta.airable.io/amazon/document/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2xpYnJhcnlcL2FydGlzdHNcLyNsaWJyYXJ5X2FydGlzdHMiXQ",  #
    "my_tracks": "https://meta.airable.io/amazon/playlist/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2xpYnJhcnlcL3RyYWNrc1wvI2xpYnJhcnlfdHJhY2tzIl0",  #
    "my_albums": "https://meta.airable.io/amazon/document/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2xpYnJhcnlcL2FsYnVtc1wvI2xpYnJhcnlfYWxidW1zIl0",  #
}

