import  json
import datetime

import os
import sys
from urllib.parse import unquote, urlencode, quote
import time, datetime
from concurrent.futures import ThreadPoolExecutor
import math

vit_prefix ="http://online.silentangel.audio/qplay?songid={}"
tidal_m3u8_path = "/mnt/vitos_player/vitos_tidal_list.m3u8"
# app_song_info= '/mnt/mpd/app_song_info'
app_song_info='./app_song_info'

def fun(jsondata):
    var = ("hours", "minutes", "seconds")
    time2sec = lambda x: int(
        datetime.timedelta(**{k: int(v) for k, v in zip(var, x.strip().split(":"))}).total_seconds())
    title = jsondata.get('title')
    album = jsondata.get('album')
    creator = jsondata.get('creator')
    duration = jsondata.get('duration')
    duration = time2sec(duration)
    songID = jsondata.get('songID')
    albumArtURI =jsondata.get('albumArtURI')
    songrate =jsondata.get("songrate")
    HQ =jsondata.get("songrate")
    protocolInfo=jsondata.get("protocolInfo")

    return f"song_begin: {vit_prefix.format(songID)}\nTitle: {title}\n" \
           f"Artist: {creator}\nAlbum: {album}\nCover: {albumArtURI}\n" \
           f"CoverPreview: {albumArtURI}\nduration: {duration}\nTime: {duration}" \
           f"\nsongrate: {songrate}\nHQ: {HQ}\nprotocolInfo: {protocolInfo}\nsong_end"


def save_song_info(data):
    playlsit=data.get("TracksMetaData")
    info_list=list(map(fun,playlsit))
    info="\n".join(list(info_list))
    with open(app_song_info,'w+')as f:
        f.write(info)
def filter_songid(data,song_id):
    songID=data.get('songID')
    return songID==song_id


def get_trackurl(data,songid):
    playlsit = data.get('TracksMetaData', [])
    song_data=list(filter(lambda seq:filter_songid(seq,song_id=songid),playlsit))[0]
    trackURIs=song_data.get('trackURIs')
    # print("".join(trackURIs))
    return "".join(trackURIs)

def qplay_parameter_dic(parameter):
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
        
def main():
    try:
        tidal_paramter = sys.argv[2]
    except:
        tidal_paramter = ''

    try:
        tidal_manage = sys.argv[1]
    except:
        tidal_manage = ''
    
    if tidal_manage == 'track_url':
        with open('/mnt/upmpdcli/qplay_queue.json')as f:
            data = json.load(f)

        parameter_dic = qplay_parameter_dic(tidal_paramter)
        track_id = parameter_dic.get('track_id')
        print(get_trackurl(data, track_id))

if __name__ == '__main__':
    main()

# l=map(fun,playlsit)
# print("\n".join(list(l)))
# print(list(l))
# get_trackurl('4934048')
# url1='http://120.41.44.14/amobile.music.tc.qq.com/M500002pl4Qg2QSyR9.mp3?guid=60C1555C06E04B719B757DBA5277BA68&vkey=02B13AE438AE11C4F1A4540BEBF4A9EBE936EE0A250DFCB8DF3FD3D9EC1D728515FD8E2B212943E091D59A1191E7E17837A766DA64112980&uin=1152921505047252502&fromtag=125'
# url2='http://120.41.44.14/amobile.music.tc.qq.com/M500002pl4Qg2QSyR9.mp3?guid=60C1555C06E04B719B757DBA5277BA68&vkey=02B13AE438AE11C4F1A4540BEBF4A9EBE936EE0A250DFCB8DF3FD3D9EC1D728515FD8E2B212943E091D59A1191E7E17837A766DA64112980&uin=1152921505047252502&fromtag=125'
# print(url1==url2)
#if __name__ == '__main__':
#    with open('/mnt/upmpdcli/demo.json')as f:
#        data = json.load(f)
#    save_song_info(data)
#
#    #传入id获取播放链接
#    print(get_trackurl(data,'334748404'))
