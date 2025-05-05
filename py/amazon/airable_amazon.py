import os
import sys
import json
from urllib.parse import unquote,urlencode,quote
import time,datetime
from concurrent.futures import ThreadPoolExecutor
import math

airable_request='airable {}'
vit_prefix = "http://online.silentangel.audio/amazon?url="
app_song_info = '/mnt/mpd/app_song_info'
amazon_m3u8_path = "/tmp/vitos_amazon_list.m3u8"
quality_info='/mnt/settings/amazon_streaming_quality.conf'
station_prefix='http://online.silentangel.audio/amazon/station?url='

def maybe_login():
    url = "https://meta.airable.io/amazon"
    data = "".join(os.popen(airable_request.format(url)).readlines()).strip()
    data = json.loads(data)
    if data.get('description') != "Use control app to log in.":
        return json.dumps({'vit_status':0,'vit_message':'',"login":True})
    else:
        try:
            login_url=data.get('buttons')[2].get('url')
        except:
            login_url=''
    return json.dumps({'vit_status':1,'vit_message':'101',"login":False,'login_url':login_url})


def check_data(data):
    try:
        data=json.loads(data)

        if data.get('description')=="Use control app to log in.":
            data['vit_status']=1
            data['vit_message']='101'
        else:
            data['vit_status']=0
            data['vit_message']=''
        return data
    except:
        return {'vit_status':4,'vit_message':'446'}

def amazon_parameter_dic(parameter):
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
def threaing_page_tracks(url, page, track_dic, flag=False):

    current_page_info = "".join(os.popen(airable_request.format(url)).readlines()).strip()
    current_page_info = check_data(data=current_page_info)
    if int(current_page_info.get('vit_status')) != 0:
        return current_page_info
    tracks = current_page_info.get('content', {}).get('entries', [])
    track_dic[page] = tracks

def get_next_page_info(url,track_list):#递归获取所有的下一页歌曲
    url = "\"" + unquote(url) + "\""
    next_page_info = "".join(os.popen(airable_request.format(url)).readlines()).strip()
    next_page_info = check_data(data=next_page_info)

    if int(next_page_info.get('vit_status'))!=0:
        return next_page_info
    tracks = next_page_info.get('content',{}).get('entries','')
    if tracks:
        track_list+=tracks
    else:
        return track_list
    #下一页链接.
    try:
        next_url=next_page_info.get('content').get('pagination').get('next')
    except:
        next_url=''
    if not next_url:
        return track_list
    else:
        return get_next_page_info(url=next_url,track_list=track_list)

def get_100_tracks(url,track_list,is_next='next'):
    url="\""+unquote(url)+"\""
    next_page_info = "".join(os.popen(airable_request.format(url)).readlines()).strip()
    next_page_info = check_data(data=next_page_info)
    if int(next_page_info.get('vit_status')) != 0:
        return next_page_info

    tracks = next_page_info.get('content', {}).get('entries', '')

    if len(track_list)<100:
        # 下一页链接.
        if is_next=='next':
            if tracks:
                track_list+=tracks
            else:
                return track_list
            next_url = quote(next_page_info.get('content',{}).get('pagination',{}).get('next',''))

            if not next_url:
                return track_list
            else:
                return get_100_tracks(url=next_url, track_list=track_list)
        elif is_next=='prev':
            if tracks:
                track_list=tracks+track_list
            else:
                return track_list
            prev_url=quote(next_page_info.get('content',{}).get('pagination',{}).get('prev',''))
            if not prev_url:
                return track_list
            else:
                return get_100_tracks(url=prev_url,track_list=track_list,is_next='prev')
    else:
        return track_list

def amazon_get_play_url(parameter):
    parameter_dic=amazon_parameter_dic(parameter)
    if isinstance(parameter_dic,str):
        return '200'
    url=parameter_dic.get('track_id','')
    if url:
        url = "\"" + unquote(url) + "\""
    else:
        return '{"vit_status":2,"vit_message":"201"}'
    data = "".join(os.popen(airable_request.format(url)).readlines()).strip()
    data = check_data(data=data)
    if data.get('vit_status')==0:
        stream=data.get('streams','')
        if not stream:
            return 'stream is None'
        else:
            stream_url = stream[0].get('url')
        track_info="".join(os.popen(airable_request.format(stream_url)).readlines()).strip()
        track_info=check_data(track_info)
        play_url=track_info.get('url')

        if play_url:
            return play_url
        else:
            return '{"vit_status":4,"vit_message":"441"}'
    else:
        return data

def amazon_add_track(parameter,flag='a+'):

    if not parameter:
        return '200'
    key_list = ['Artist', 'Album', 'AlbumArtist', 'Title', 'Track', 'Genre', 'Date',
                'Cover', 'CoverPreview', 'Label', 'Composer', 'Time', 'duration', 'Format']
    track_id=''
    model= 'insert'
    params=''
    import urllib.parse
    for param in parameter.split('&'):
        if -1==param.find('='):
            continue
        key =param.split('=',1)[0]
        value=urllib.parse.unquote(param.split('=',1)[1])
        if not value:
            continue
        if 'track_url'==key:
            track_uri=value
        elif 'model'==key:
            model=value
        elif key in key_list:
            params += '{}: {}\n'.format(key, value)
    if not track_uri:
        return '{"vit_status":2,"vit_message":"201"}'
    track_url=vit_prefix+track_uri

    info ='song_begin: {}\n{}song_end\n'.format(track_url,params)

    info_dir=os.path.dirname(app_song_info)

    if not os.path.exists(info_dir):
        os.makedirs(info_dir)
    with open(app_song_info, flag, encoding='utf8')as f:
        f.write(info)
    if flag=='w+':
        os.system('mpc clear > /dev/null 2>&1 && mpc add {}  > /dev/null 2>&1 && mpc play > /dev/null 2>&1'.format(
            track_url))
    else:
        if 'insert' == model:
            os.system('mpc insert {}  > /dev/null 2>&1'.format(track_url))
        else:
            os.system('mpc add {}  > /dev/null 2>&1'.format(track_url))

    return '{"vit_status":0,"vit_message":"' + track_id + '"}'

def amazon_play_album(parameter,type):
    parameter_dic=amazon_parameter_dic(parameter)
    if isinstance(parameter_dic,str):
        return 200
    album_url=parameter_dic.get('album_url','')
    if not album_url:
        return '{"vit_status":2,"vit_message":201}'
    else:
        album_url = "\"" + album_url + "\""
    track_url = parameter_dic.get('track_url')

    album_info = "".join(os.popen(airable_request.format(album_url)).readlines()).strip()
    album_info = check_data(data=album_info)

    if int(album_info.get('vit_status'))==0:
        tracks = album_info.get('content',{}).get('entries')
        sun = []
        for index, track in enumerate(tracks):  # 遍历当前页的track 如果没有返回歌曲的url则返回提示
            track_uri = track.get('url')
            if track_uri:
                sun.append(track_uri)
        if not sun:
            print('{"vit_status":4,"vit_message":"403"}')
            sys.exit(403)

        pages_value = album_info.get('content', {}).get('pagination', {}).get('pages', {}).get('values', [])
        if pages_value:

            current = album_info.get('content', {}).get('pagination', {}).get('pages',{}).get('current')
            current_index = pages_value.index(current)  # 当前页的index
            page1 = pages_value[current_index:]
            page2 = pages_value[:current_index]
            pages_value = page1 + page2
            pages_value.remove(current)
            if pages_value:
                track_dic = {}
                # 创建线程池
                threadPool = ThreadPoolExecutor(max_workers=6)
                for page in pages_value[:4]:
                    threadPool.submit(threaing_get_tracks, album_url, page, track_dic)
                threadPool.shutdown(wait=True)

                for k in pages_value[:4]:
                    tracks += track_dic[k]

    info_public=''
    info_public+='{}: {}\n'.format('Album', album_info.get('title'))

    dict_track = {"artist": 'Artist', 'title': 'Title','duration': 'Time','cover': 'CoverPreview'}
    info,track_all,play_index =append_song_info(dict_track,info_public,track_url,tracks)
    return save_song_info_and_play(info,album_url,track_all,type=type)

def threaing_get_tracks(url, page, track_dic):
    url += f"?p={page}"
    url = "\"" + unquote(url) + "\""
    for i in range(3):
        current_page_info = "".join(os.popen(airable_request.format(url)).readlines()).strip()
        current_page_info = check_data(data=current_page_info)
        if int(current_page_info.get('vit_status')) != 0:
            continue
        tracks = current_page_info.get('content', {}).get('entries', [])
        if tracks:
            break
    track_dic[page] = tracks


def get_all_tracks(url,tracks_list=[]):
    # url = "\"" + unquote(url) + "\""
    current_page_info = "".join(os.popen(airable_request.format(url)).readlines()).strip()
    current_page_info = check_data(data=current_page_info)
    if int(current_page_info.get('vit_status')) != 0:
        return current_page_info
    tracks = current_page_info.get('content', {}).get('entries', '')
    sun = []
    for index, track in enumerate(tracks):  # 遍历当前页的track 如果没有返回歌曲的url则返回提示
        track_uri = track.get('url')
        if track_uri:
            sun.append(track_uri)
    if not sun:
        print('{"vit_status":4,"vit_message":"403"}')
        sys.exit(403)
    else:
        tracks_list += tracks
    pages_value = current_page_info.get('content', {}).get('pagination', {}).get('pages', {}).get('values', [])
    if pages_value:
        current = current_page_info.get('content', {}).get('pagination', {}).get('pages', {}).get('current', '')
        current_index = pages_value.index(current)  # 当前页的index
        page1 = pages_value[current_index:]
        page2 = pages_value[:current_index]
        pages_value = page1 + page2
        pages_value.remove(current)
    #if pages_value:
        track_dic = {}
        # 创建线程池
        threadPool = ThreadPoolExecutor(max_workers=6)
        for page in pages_value:
            threadPool.submit(threaing_get_tracks,url, page, track_dic)
        threadPool.shutdown(wait=True)
        for k in pages_value:
            tracks=track_dic.get(k)
            if tracks:
                tracks_list += tracks
    return tracks_list

def amazon_play_playlist(parameter,type):
    parameter_dic = amazon_parameter_dic(parameter)
    if isinstance(parameter_dic, str):
        return '200'

    playlist_url = parameter_dic.get('playlist_url')
    if not playlist_url:
        return '{"vit_status":2,"vit_message":201}'

    track_url = parameter_dic.get('track_url')

    # tracks = get_next_page_info(url=playlist_url, track_list=[])
    tracks=get_all_tracks(url=playlist_url)
    dict_track = {'title': 'Title', "artist": 'Artist', 'album': 'Album',
                  'release': 'Date', 'cover': 'CoverPreview', 'duration': 'Time'}
    info_public = ''
    info, track_all, play_index = append_song_info(dict_track, info_public, track_url, tracks)

    return save_song_info_and_play(info, playlist_url, track_all, type=type)



def save_song_info_and_play(info, url, track_all,type):

    info_dir = os.path.dirname(app_song_info)
    if not os.path.exists(info_dir):
        os.makedirs(info_dir)
    with open(app_song_info, type, encoding='utf8')as f:
        f.write(info)

    with open(amazon_m3u8_path, mode='w+', encoding='utf8')as f3:
        f3.write(''.join(track_all))
    if type=='w+':
        os.system('mpc clear > /dev/null 2>&1 && mpc load {}  > /dev/null 2>&1 && mpc play 1 > /dev/null 2>&1'.format(amazon_m3u8_path))
    elif type=='a+':
        os.system('mpc load {}  > /dev/null 2>&1'.format(amazon_m3u8_path))
    return '{"vit_status":0,"vit_message":"' + url.replace("\"",'') + '"}'


def amazon_get_station_play_url(parameter):

    parameter_dic=amazon_parameter_dic(parameter)
    if isinstance(parameter_dic,str):
        return '200'
    url=parameter_dic.get('track_id','')


    data = "".join(os.popen(airable_request.format(url)).readlines()).strip()
    data = check_data(data=data)

    if data.get('vit_status')==0:
        current_track_info = get_station_info(data,url)
        info_dir = os.path.dirname(app_song_info)
        if not os.path.exists(info_dir):
            os.makedirs(info_dir)

        with open(app_song_info, mode='w+', encoding='utf8')as f:
            f.write(current_track_info)

        current_track=data.get('content',{}).get('entries')[0]
        if not current_track:
            return json.dumps({'vit_status':4,'vit_message':'444'})
        stream_url=current_track.get('streams')[0].get('url','')
        track_info="".join(os.popen(airable_request.format(stream_url)).readlines()).strip()
        track_info=check_data(track_info)
        play_url=track_info.get('url')

        prev_url = data.get('content', {}).get('pagination', {}).get('prev', '')
        next_url = data.get('content', {}).get('pagination', {}).get('next', '')

        if play_url:
            return play_url,prev_url,next_url
        else:
            return '{"vit_status":4,"vit_message":"441"}'
    else:
        return data

def get_station_info(data,url):
    try:
        track=data.get('content',{}).get('entries')[0]
    except:
        print(json.dumps(data))
        sys.exit(0)
    if not track:
        return json.dumps({'vit_status':4,'vit_message':'444'})

    station_cover=data.get("images","")[0].get('url')
    station_title=data.get("title","")[0]
    info_public =f'StationTitle: {station_title}\nStationCover: {station_cover}\n'

    track_url = f"{station_prefix}{url}\n"
    info = 'song_begin: {}'.format(track_url)
    dict_track = {'title': 'Title', "artist": 'Artist', 'album': 'Album', 'cover': 'CoverPreview', 'duration': 'Time'}
    for key in dict_track:
        if key == 'artist' or key == 'album':
            value = track.get(key, {}).get('title', '').replace('\n', '')
        elif key == 'cover':
            value = track.get('images', '')
            if value:
                cover = value[-1].get('url', '')
                coverpreview = value[-1].get('url', '')
                info += f'Cover: {cover}\nCoverPreview: {coverpreview}\n'
                continue
            else:
                continue
        else:
            value = str(track.get(key, '')).replace('\n', '')
        if not value:
            continue
        mpd_key = dict_track[key]
        if key == 'duration':
            info += f'duration: {value}\n'
        info += f'{mpd_key}: {value}\n'
    info += info_public + 'song_end\n'
    return info


def amazon_play_station(parameter):
    parameter_dic = amazon_parameter_dic(parameter)
    station_url=parameter_dic.get('station_url')
    if not station_url:
        return json.dumps({'vit_status':2,'vit_message':'201'})
    current_track_url = f"{station_prefix}{station_url}\n"
    os.system(
        'mpc clear > /dev/null 2>&1 && mpc add {} > /dev/null 2>&1 && mpc play > /dev/null 2>&1'.format(
            current_track_url))

    os.system('mpc repeat off > /dev/null 2>&1')
    os.system('mpc single off > /dev/null 2>&1')
    os.system('mpc random off > /dev/null 2>&1')
    return json.dumps({"vit_status":0,"vit_message":current_track_url.replace("\"", '')})

def append_song_info(dic_track,info_public,song_url,tracks):
    play_index=-1
    info=''
    track_all=[]

    for index,track in enumerate(tracks):
        track_uri=track.get('url','')
        if not track_uri:
            continue

        if str(song_url)==str(track_uri):
            play_index=index

        track_url = f"{vit_prefix}{track_uri}\n"

        if -1==play_index:
            track_all.append(track_url)
        else:
            track_all.insert(index-play_index,track_url)

        info += 'song_begin: {}'.format(track_url)
        for key in dic_track.keys():
            if key=='artist' or key=='album':
                value=track.get(key,{}).get('title','').replace('\n','')

            elif key =='cover':
                value=track.get('images','')
                if value:
                    cover=value[-1].get('url','')
                    coverpreview=value[-1].get('url','')
                    info += f'Cover: {cover}\nCoverPreview: {coverpreview}\n'
                    continue
                else:
                    continue

            else:
                value=str(track.get(key,'')).replace('\n','')
            if not value:
                continue
            mpd_key=dic_track[key]
            if key =='duration':
                info+=f'duration: {value}\n'
            info += f'{mpd_key}: {value}\n'
        info += info_public + 'song_end\n'
    return info, track_all, play_index

def amazon_play_my_track(parameter,type):
    parameter_dic=amazon_parameter_dic(parameter)
    if isinstance(parameter_dic, str):
        return '200'

    track_url = parameter_dic.get('track_url')
    current=int(parameter_dic.get('page',1))  # airable返回数据没有页数信息，改成默认值为1
    size=parameter_dic.get('size')

    url="\""+'https://meta.airable.io/amazon/playlist/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2xpYnJhcnlcL3RyYWNrc1wvI2xpYnJhcnlfdHJhY2tzIl0?p={}'+"\""
    if not track_url or track_url=="没有该字段":
        return '{"vit_status":4,"vit_message":"403"}'
    if not current:
        return '{"vit_status":2,"vit_message":"202"}'
    if size:
        size=int(size)
        page_list = [i for i in range(1, math.ceil(size) + 1)]

        track_list = []
        current_index = page_list.index(current)  # 当前页的index
        page1 = page_list[current_index:]
        page2 = page_list[:current_index]
        pages = page1 + page2

        # pages.remove(current)
        if pages:
            # 创建线程池
            threadPool = ThreadPoolExecutor(max_workers=6)
            track_dic = {}
            for i in pages[:5]:
                threadPool.submit(threaing_page_tracks, url.format(i), i, track_dic)
            threadPool.shutdown(wait=True)

            for k in pages[:5]:
                track_list += track_dic[k]
            sun = []
            for index, track in enumerate(track_list[:20]):  # 遍历当前页的track 如果没有返回歌曲的url则返回提示
                track_uri = track.get('url')
                if track_uri:
                    sun.append(track_uri)
            if not sun:
                print('{"vit_status":4,"vit_message":"403"}')
                sys.exit(403)
    else:
        current_url=url.format(current)
        current_page_info = "".join(os.popen(airable_request.format(current_url)).readlines()).strip()
        current_page_info = check_data(data=current_page_info)
        if int(current_page_info.get('vit_status')) != 0:
            return current_page_info
        track_list = current_page_info.get('content', {}).get('entries', '')
        sun = []
        for index, track in enumerate(track_list):  # 遍历当前页的track 如果没有返回歌曲的url则返回提示
            track_uri = track.get('url')
            if track_uri:
                sun.append(track_uri)
        if not sun:
            print('{"vit_status":4,"vit_message":"403"}')
            sys.exit(403)

        pages_value = current_page_info.get('content', {}).get('pagination', {}).get('pages', {}).get('values', [])
        if not pages_value:  # airable返回数据没有页数信息，改成默认值为1
            pages_value = [1]
        current_index = pages_value.index(current)  # 当前页的index
        page1 = pages_value[current_index:]
        page2 = pages_value[:current_index]
        pages_value = page1 + page2
        pages_value.remove(current)
        if pages_value:
            track_dic = {}
            # 创建线程池
            threadPool = ThreadPoolExecutor(max_workers=6)
            for page in pages_value[:4]:
                threadPool.submit(threaing_get_tracks, url, page, track_dic)
            threadPool.shutdown(wait=True)
            for k in pages_value[:4]:
                track_list += track_dic[k]


    dict_track = {'title': 'Title', "artist": 'Artist', 'album': 'Album',
                  'release': 'Date', 'cover': 'CoverPreview', 'duration': 'Time'}
    info_public = ''
    info, track_all, play_index = append_song_info(dict_track, info_public, track_url, track_list)

    if -1 != play_index:
        return save_song_info_and_play(info, track_url, track_all, type=type)
    try:
        track_info = "".join(os.popen(airable_request.format(track_url)).readlines()).strip()
        track_info =check_data(track_info)
        vit_status = track_info.get('vit_status')
        if vit_status == 0:

            play_track_url = f'{vit_prefix}{track_url}\n'
            track_all.insert(0, play_track_url)
            info += 'song_begin: {}'.format(play_track_url)

            dict_track = {'title': 'Title', "artist": 'Artist', 'album': 'Album',
                          'release': 'Date', 'cover': 'CoverPreview', 'duration': 'Time'}
            for key in dict_track.keys():
                if key == 'artist' or key=='album':
                    value = track_info.get(key).get('title')
                elif 'cover' == key:
                    value = track_info.get('image')
                    if value:
                        cover = value[-1]
                        coverpreview = value[-1]
                        info += f'Cover: {cover}\nCoverPreview: {coverpreview}\n'
                        continue
                    else:
                        continue
                else:
                    value = track_info.get(key)
                if not value:
                    continue
                if key == 'duration':
                    info += f'duration: {value}'
                info += '{}: {}\n'.format(dict_track[key], value)
            info += 'song_end\n'
            return save_song_info_and_play(info,track_url, track_all, type=type)
    except:
        return '{"vit_status":4,"vit_message":"886"}'



def amazon_play_artist_tracks(parameter,type):
    parameter_dic = amazon_parameter_dic(parameter)
    if isinstance(parameter_dic, str):
        return '200'
    artist_track_url = parameter_dic.get('url')
    track_url = parameter_dic.get('track_url')
    current = int(parameter_dic.get("page",1))
    if not artist_track_url:
        return '{"vit_status":2,"vit_message":"201"}'
    elif not track_url:
        return '{"vit_status":2,"vit_message":"202"}'
    elif not current:
        return '{"vit_status":2,"vit_message":"203"}'
    else:
        artist_track_url = "\""+artist_track_url+'?p={}'+"\""
        track_list=[]
        page_list = [i for i in range(1,6)]
        current_index=page_list.index(current)
        page1 = page_list[current_index:]
        page2 = page_list[:current_index]
        pages = page1 + page2


        threadPool = ThreadPoolExecutor(max_workers=6)
        track_dic = {}
        for i in pages:
            threadPool.submit(threaing_page_tracks, artist_track_url.format(i), i, track_dic)
        threadPool.shutdown(wait=True)
        for k in pages:
            track_list += track_dic[k]
        sun = []
        for index, track in enumerate(track_list[:20]):  # 遍历当前页的track 如果没有返回歌曲的url则返回提示
            track_uri = track.get('url')
            if track_uri:
                sun.append(track_uri)
        if not sun:
            print('{"vit_status":4,"vit_message":"403"}')
            sys.exit(403)

        dict_track = {'title': 'Title', "artist": 'Artist', 'album': 'Album',
              'release': 'Date','cover': 'CoverPreview','duration': 'Time'}
        info_public = ''
        info, track_all, play_index = append_song_info(dict_track, info_public, track_url,track_list)
        return save_song_info_and_play(info, artist_track_url, track_all, type=type)

def amazon_play_hundred_tracks(parameter,url,type):
    parameter_dic = amazon_parameter_dic(parameter)
    if isinstance(parameter_dic, str):
        return '200'
    track_url = parameter_dic.get('track_url')
    current =parameter_dic.get('page','1')#当前页

    size =parameter_dic.get('size')#歌曲的总数


    if not track_url or track_url == '没有该字段':
        return '{"vit_status":4,"vit_message":403}'
    if not current:
        return '{"vit_status":2,"vit_message":"202"}'
    else:
        current=int(current)
    if size:
        size =int(size)
        page_lsit=[i for i in range(1,math.ceil((size/20)+1))]
        current_index=page_lsit.index(current)

        page1= page_lsit[current_index:]
        page2= page_lsit[:current_index]
        pages=page1+page2

        if pages:
            tracks=[]
            threadPool = ThreadPoolExecutor(max_workers=6)
            track_dic = {}
            for i in pages[:5]:
                threadPool.submit(threaing_page_tracks, url.format(i), i, track_dic)
            threadPool.shutdown(wait=True)
            for k in pages[:5]:
                tracks += track_dic[k]
            sun = []
            for index, track in enumerate(tracks[:20]):  # 遍历当前页的track 如果没有返回歌曲的url则返回提示
                track_uri = track.get('url')
                if track_uri:
                    sun.append(track_uri)
            if not sun:
                print('{"vit_status":4,"vit_message":"403"}')
                sys.exit(403)
    else:
        current_url = url.format(current)
        info = "".join(os.popen(airable_request.format(current_url)).readlines()).strip()

        info = check_data(info)

        if int(info.get('vit_status')) != 0:
            return info

        tracks = info.get('content').get('entries')
        sun = []
        for index, track in enumerate(tracks):  # 遍历当前页的track 如果没有返回歌曲的url则返回提示
            track_uri = track.get('url')
            if track_uri:
                sun.append(track_uri)
        if not sun:
            print('{"vit_status":4,"vit_message":"403"}')
            sys.exit(403)

        current = info.get('content', {}).get('pagination', {}).get('pages').get('current')  # 当前页的页码
        page_list = info.get('content', {}).get('pagination', {}).get('pages').get('values')  # 所有的页码
        current_index = page_list.index(current)  # 当前页的index

        page1 = page_list[current_index:]
        page2 = page_list[:current_index]
        pages = page1 + page2
        pages.remove(current)

        if pages:
            # 创建线程池
            threadPool = ThreadPoolExecutor(max_workers=6)
            track_dic = {}
            for i in pages[:4]:
                threadPool.submit(threaing_page_tracks, url.format(i), i, track_dic)
            threadPool.shutdown(wait=True)
            for k in pages[:4]:
                tracks += track_dic[k]




    dict_track = {'title': 'Title', "artist": 'Artist', 'album': 'Album',
                  'release': 'Date', 'cover': 'CoverPreview', 'duration': 'Time'}
    info_public = ''
    info, track_all, play_index = append_song_info(dict_track, info_public, track_url, tracks)

    if -1 != play_index:
        return save_song_info_and_play(info, track_url, track_all, type=type)

    try:
        track_info = "".join(os.popen(airable_request.format(track_url)).readlines()).strip()
        track_info = check_data(track_info)
        vit_status = track_info.get('vit_status')
        if vit_status == 0:

            play_track_url = f'{vit_prefix}{track_url}\n'
            track_all.insert(0, play_track_url)
            info += 'song_begin: {}'.format(play_track_url)

            dict_track = {'title': 'Title', "artist": 'Artist', 'album': 'Album',
                          'release': 'Date', 'cover': 'CoverPreview', 'duration': 'Time'}
            for key in dict_track.keys():
                if key == 'artist' or key == 'album':
                    value = track_info.get(key).get('title')
                elif 'cover' == key:
                    value = track_info.get('image')
                    if value:
                        cover = value[-1]
                        coverpreview = value[-1]
                        info += f'Cover: {cover}\nCoverPreview: {coverpreview}\n'
                        continue
                    else:
                        continue
                else:
                    value = track_info.get(key)
                if not value:
                    continue
                if key == 'duration':
                    info += f'duration: {value}'
                info += '{}: {}\n'.format(dict_track[key], value)
            info += 'song_end\n'
            return save_song_info_and_play(info, play_track_url, track_all, type=type)
    except:
        return '{"vit_status":4,"vit_message":"886"}'
def amazon_play_seach_tracks(parameter,type):
    parameter_dic = amazon_parameter_dic(parameter)
    if isinstance(parameter_dic, str):
        return '200'
    query = parameter_dic.get('query').replace(' ','%20')
    if not query:
        return '{"vit_status":2,"vit_message":"201"}'


    track_url = parameter_dic.get('track_url')#从搜索中选中的歌曲url

    current =parameter_dic.get('page')#选中歌曲的当前页

    size = int(parameter_dic.get('size','50'))#搜索到的歌曲数目

    if not track_url or track_url=="没有该字段":
        return '{"vit_status":4,"vit_message":"403"}'

    if not current:
        return '{"vit_status":2,"vit_message":"203"}'
    else:
        current=int(current)
    url = parameter_dic.get("url")  # 获取搜索歌曲的url

    if not url:#如果参数中不包含获取搜索歌曲的链接则根据搜索关键子进行搜索
        url = 'https://meta.airable.io/amazon/search?q={}'.format(query)
        data = "".join(os.popen(airable_request.format(url)).readlines()).strip()
        data = check_data(data)
        if data.get('vit_status') != 0:
            return data
        else:
            types = data.get('content', {}).get('entries', {})
            for seach in types:
                if seach.get('title', '') == 'Amazon Music':
                    seach_url = seach.get('url')
                    break
            data = "".join(os.popen(airable_request.format(seach_url)).readlines()).strip()
            data = check_data(data)
            seach_type = data.get('content', {}).get('entries', {})
            for seach in seach_type:
                title = seach.get('title', '')
                if 'Songs' == title:
                    url = seach.get('url')
                    data = "".join(os.popen(airable_request.format(url)).readlines()).strip()
                    seach_info = check_data(data)
                    break
            if int(seach_info.get('vit_status')) != 0:
                return seach_info
            url=seach_info.get('url')
    url = url+'?p={}'
    page_list = [i for i in range(1, math.ceil(size) + 1)]


    current_index = page_list.index(current)  # 当前页的index
    page1 = page_list[current_index:]
    page2 = page_list[:current_index]
    pages = page1 + page2

    track_list = []
    # 创建线程池
    threadPool = ThreadPoolExecutor(max_workers=6)
    track_dic = {}
    for i in pages[:5]:
        threadPool.submit(threaing_page_tracks, url.format(i), i, track_dic)
    threadPool.shutdown(wait=True)

    for k in pages[:5]:
        track_list += track_dic[k]
    sun = []
    for index, track in enumerate(track_list[:20]):  # 遍历当前页的track 如果没有返回歌曲的url则返回提示
        track_uri = track.get('url')
        if track_uri:
            sun.append(track_uri)
    if not sun:
        print('{"vit_status":4,"vit_message":"403"}')
        sys.exit(403)

    dict_track = {'title': 'Title', "artist": 'Artist', 'album': 'Album',
                  'release': 'Date', 'cover': 'CoverPreview', 'duration': 'Time'}

    info_public = ''
    info, track_all, play_index = append_song_info(dict_track, info_public, track_url, track_list)

    if -1 != play_index:
        return save_song_info_and_play(info, track_url, track_all, type=type)

    try:
        track_info = "".join(os.popen(airable_request.format(track_url)).readlines()).strip()
        track_info = check_data(track_info)
        vit_status = track_info.get('vit_status')
        if vit_status == 0:

            play_track_url = f'{vit_prefix}{track_url}\n'
            track_all.insert(0, play_track_url)
            info += 'song_begin: {}'.format(play_track_url)

            dict_track = {'title': 'Title', "artist": 'Artist', 'album': 'Album',
                          'release': 'Date', 'cover': 'CoverPreview', 'duration': 'Time'}
            for key in dict_track.keys():
                if key == 'artist' or key == 'album':
                    value = track_info.get(key).get('title')
                elif 'cover' == key:
                    value = track_info.get('image')
                    if value:
                        cover = value[-1]
                        coverpreview = value[-1]
                        info += f'Cover: {cover}\nCoverPreview: {coverpreview}\n'
                        continue
                    else:
                        continue
                else:
                    value = track_info.get(key)
                if not value:
                    continue
                if key == 'duration':
                    info += f'duration: {value}'
                info += '{}: {}\n'.format(dict_track[key], value)
            info += 'song_end\n'
            return save_song_info_and_play(info, play_track_url, track_all, type=type)
    except:
        return '{"vit_status":4,"vit_message":"886"}'


def request(url):
    data = "".join(os.popen(airable_request.format(url)).readlines()).strip()
    data = check_data(data)
    print(json.dumps(data))

def colligate_search(seach_type,parameter):
    parameter_dic=amazon_parameter_dic(parameter)

    query=parameter_dic.get('query','').replace(' ','%20')
    if not query:
        print(json.dumps({'vit_status':2,'vit_message':'201'}))
        sys.exit(201)
    url='https://meta.airable.io/amazon/search?q={}'.format(query)
    data = "".join(os.popen(airable_request.format(url)).readlines()).strip()
    data=check_data(data)
    types=data.get('content',{}).get('entries',{})

    for seach in types:
        if seach.get('title','')=='Amazon Music':
            seach_url=seach.get('url')
            break
    data = "".join(os.popen(airable_request.format(seach_url)).readlines()).strip()
    data = check_data(data)

    seach_types =data.get('content', {}).get('entries', {})
    for type_seach in seach_types:
        title=type_seach.get('title','')
        if seach_type==title:
            url =type_seach.get('url')
            request(url)

def amazon_logout():
    logout_url = 'https://meta.airable.io/amazon/logout'
    info = ''
    skip_tidal = False
    try:
        os.system('mpc playlistdel http://online.silentangel.audio/amazon > /dev/null 2>&1')
        with open(app_song_info, encoding='utf8')as f:
            for line in f:
                if line.startswith('song_begin: ' + vit_prefix):
                    skip_tidal = True
                if skip_tidal:
                    if line.startswith('song_end'):
                        skip_tidal = False
                    continue
                else:
                    info += line
        with open(app_song_info, 'w+', encoding='utf8')as f:
            f.write(info)
    except:
        pass
    data = "".join(os.popen(airable_request.format(logout_url)).readlines()).strip()
    data = check_data(data)
    os.popen('find /mnt/streaming_cache/amazon/ -type f -mtime -1 -name "*" -exec rm -rf {} \; > /dev/null 2>&1')
    return data

def main():
    try:
        amazon_parameter =sys.argv[2]
    except:
        amazon_parameter=''
    try:
        amazon_manage=sys.argv[1]
    except:
        amazon_manage=''
    if amazon_manage == "common":
        parameter_dic = amazon_parameter_dic(amazon_parameter)
        if isinstance(parameter_dic, str):
            print('200')
            sys.exit(200)
        url = parameter_dic.get('url', '')
        if not url:
            print(json.dumps({'vit_status': 2, 'vit_message': '201'}))
            sys.exit(201)
        url = "\"" + unquote(url) + "\""
        data = "".join(os.popen(airable_request.format(url)).readlines()).strip()
        data = check_data(data)
        print(json.dumps(data))
    elif amazon_manage=='maybe_login':
        print(maybe_login())
    elif  amazon_manage=='index':
        url="https://meta.airable.io/amazon"
        request(url)
# --------------------------------------------------------------------------2.new-------------------------------------------------------------------------------
    elif amazon_manage=='new_playlist':
        url='https://meta.airable.io/amazon/document/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2NhdGFsb2dcL25ld1wvcGxheWxpc3RzXC8jbmV3X3BsYXlsaXN0c19kZXNjIl0'
        request(url)
    elif amazon_manage=='new_album':
        url='https://meta.airable.io/amazon/document/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2NhdGFsb2dcL25ld1wvYWxidW1zXC8jbmV3X2FsYnVtc19kZXNjIl0'
        request(url)
    elif amazon_manage=='new_track':
        url='https://meta.airable.io/amazon/playlist/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2NhdGFsb2dcL25ld1wvdHJhY2tzXC8jbmV3X3RyYWNrc19kZXNjIl0'
        request(url)
#---------------------------------------------------------------------------3.playlist--------------------------------------------------------------------------
    elif amazon_manage=='all_playlist':
        url = 'https://meta.airable.io/amazon/document/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2NhdGFsb2dcL25ld1wvcGxheWxpc3RzXC8jbmV3X3BsYXlsaXN0c19kZXNjIl0'
        request(url)
    elif amazon_manage=='recently_played':
        url='https://meta.airable.io/amazon/document/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2NhdGFsb2dcL3BsYXlsaXN0c1wvcmVjZW50XC8jcmVjZW50bHlfcGxheWVkX3BsYXlsaXN0cyJd'
        request(url)
    elif amazon_manage=='genres':
        url='https://meta.airable.io/amazon/document/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2NhdGFsb2dcL3BsYXlsaXN0c1wvI3JlZmluZV9nZW5yZXMiXQ'
        request(url)
    elif amazon_manage=='moods_activities':
        url='https://meta.airable.io/amazon/document/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2NhdGFsb2dcL3BsYXlsaXN0c1wvI3JlZmluZV9tb29kc19hbmRfYWN0aXZpdGllcyJd'
        request(url)
# ----------------------------------------------------------------------------4.Recommended---------------------------------------------------------------------
    elif amazon_manage=='playlist_for_you':
        url='https://meta.airable.io/amazon/document/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2NhdGFsb2dcL3JlY3NcL3BsYXlsaXN0c1wvI3JlY3NfcGxheWxpc3RzX2Rlc2MiXQ'
        request(url)
    elif amazon_manage=='album_for_you':
        url='https://meta.airable.io/amazon/document/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2NhdGFsb2dcL3JlY3NcL2FsYnVtc1wvI3JlY3NfYWxidW1zX2Rlc2MiXQ'
        request(url)
    elif amazon_manage=='track_for_you':
        url='https://meta.airable.io/amazon/playlist/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2NhdGFsb2dcL3JlY3NcL3RyYWNrc1wvI3JlY3NfdHJhY2tzX2Rlc2MiXQ'
        request(url)
    elif amazon_manage=='station_for_you':
        url='https://meta.airable.io/amazon/document/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2NhdGFsb2dcL3JlY3NcL3N0YXRpb25zXC8jcmVjc19zdGF0aW9uc19kZXNjIl0'
        request(url)
#---------------------------------------------------------------------------------6.Charts------------------------------------------------------------------------
    elif amazon_manage=='top_playlists':
        url='https://meta.airable.io/amazon/document/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2NhdGFsb2dcL3BvcHVsYXJcL3BsYXlsaXN0c1wvI3BvcHVsYXJfcGxheWxpc3RzX2Rlc2MiXQ'
        request(url)
    elif amazon_manage=='top_albums':
        url='https://meta.airable.io/amazon/document/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2NhdGFsb2dcL3BvcHVsYXJcL2FsYnVtc1wvI3BvcHVsYXJfYWxidW1zX2Rlc2MiXQ'
        request(url)
    elif amazon_manage=='top_tracks':
        url='https://meta.airable.io/amazon/playlist/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2NhdGFsb2dcL3BvcHVsYXJcL3RyYWNrc1wvI3BvcHVsYXJfdHJhY2tzX2Rlc2MiXQ'
        request(url)
    elif amazon_manage=='top_stations':
        url='https://meta.airable.io/amazon/document/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2NhdGFsb2dcL3BvcHVsYXJcL3N0YXRpb25zXC8jcG9wdWxhcl9zdGF0aW9uc19kZXNjIl0'
        request(url)
#--------------------------------------------------------------------------------------------------7.My Music-----------------------------------------------------
    elif amazon_manage=='my_playlists':
        url='https://meta.airable.io/amazon/document/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2xpYnJhcnlcL3BsYXlsaXN0c1wvI2xpYnJhcnlfcGxheWxpc3RzIl0'
        request(url)
    elif amazon_manage=='my_artists':
        url='https://meta.airable.io/amazon/document/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2xpYnJhcnlcL2FydGlzdHNcLyNsaWJyYXJ5X2FydGlzdHMiXQ'
        request(url)
    elif amazon_manage=='my_tracks':
        url='https://meta.airable.io/amazon/playlist/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2xpYnJhcnlcL3RyYWNrc1wvI2xpYnJhcnlfdHJhY2tzIl0'
        request(url)
    elif amazon_manage=='my_albums':
        url='https://meta.airable.io/amazon/document/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2xpYnJhcnlcL2FsYnVtc1wvI2xpYnJhcnlfYWxidW1zIl0'
        request(url)
#-------------------------------------------------------------------------8.seach---------------------------------------------------------
    elif amazon_manage=='seach_artists':
        colligate_search(seach_type='Artists',parameter=amazon_parameter)
    elif amazon_manage=='seach_albums':
        colligate_search(seach_type='Albums',parameter=amazon_parameter)
    elif amazon_manage=='seach_tracks':
        colligate_search(seach_type='Songs',parameter=amazon_parameter)
    elif amazon_manage=='seach_playlists':
        colligate_search(seach_type='Playlists',parameter=amazon_parameter)
    elif amazon_manage=='seach_stations':
        colligate_search(seach_type='Stations',parameter=amazon_parameter)

#-------------------------------------------------------------------------------------------9.登出------------------------------------------------------
    elif amazon_manage=='logout':
        print(amazon_logout())
#------------------------------------------------------------------------播放相关------------------------------------------------------------------------
    elif amazon_manage=='track_url':
        print(amazon_get_play_url(parameter=amazon_parameter))
    elif amazon_manage=='add_track':
        print(amazon_add_track(parameter=amazon_parameter))
    elif amazon_manage== 'play_album':
        print(amazon_play_album(parameter=amazon_parameter, type='w+'))
    elif amazon_manage == 'playlist_add_album':
        print(amazon_play_album(parameter=amazon_parameter,type='a+'))
    elif amazon_manage == 'play_playlist':
        print(amazon_play_playlist(parameter=amazon_parameter, type='w+'))
    elif amazon_manage == 'playlist_add_playlist':
        print(amazon_play_playlist(parameter=amazon_parameter, type='a+'))
    elif amazon_manage == 'play_my_track':
        print(amazon_play_my_track(parameter=amazon_parameter, type='w+'))
    elif amazon_manage=='play_seach_track':
        print(amazon_play_seach_tracks(parameter=amazon_parameter,type='w+'))


    elif amazon_manage=='add_seach_track':
        print(amazon_play_seach_tracks(parameter=amazon_parameter,type='a+'))
    elif amazon_manage=='play_artist_track':
        print(amazon_play_artist_tracks(parameter=amazon_parameter,type='w+'))
    elif amazon_manage=='add_artist_track':
        print(amazon_play_artist_tracks(parameter=amazon_parameter,type='a+'))
    elif amazon_manage == 'play_new_tracks':
        url='https://meta.airable.io/amazon/playlist/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2NhdGFsb2dcL25ld1wvdHJhY2tzXC8jbmV3X3RyYWNrc19kZXNjIl0?p={}'
        print(amazon_play_hundred_tracks(parameter=amazon_parameter,url=url,type='w+'))
    elif amazon_manage == 'play_track_for_you':
        url='https://meta.airable.io/amazon/playlist/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2NhdGFsb2dcL3JlY3NcL3RyYWNrc1wvI3JlY3NfdHJhY2tzX2Rlc2MiXQ?p={}'
        print(amazon_play_hundred_tracks(parameter=amazon_parameter,url=url,type='w+'))

    elif amazon_manage =='play_top_tracks':
        url='https://meta.airable.io/amazon/playlist/WyJodHRwczpcL1wvbXVzaWMtYXBpLmFtYXpvbi5jb21cL2NhdGFsb2dcL3BvcHVsYXJcL3RyYWNrc1wvI3BvcHVsYXJfdHJhY2tzX2Rlc2MiXQ?p={}'
        print(amazon_play_hundred_tracks(parameter=amazon_parameter,url=url,type='w+'))




    elif amazon_manage=='play_station':
        print(amazon_play_station(parameter=amazon_parameter))
    elif amazon_manage=='get_play_station_url':
        os.system(f'mpc crop > /dev/null 2>&1')
        play_url,prev_url,next_url=amazon_get_station_play_url(parameter=amazon_parameter)

        print(play_url)

        if prev_url:
            prev_track_url = f"{station_prefix}{prev_url}\n"
            os.system(f'mpc add {prev_track_url} > /dev/null 2>&1')
            os.system(f'mpc move 2 1 > /dev/null 2>&1')
        if next_url:
            next_track_url = f"{station_prefix}{next_url}\n"
            os.system(f'mpc add {next_track_url} > /dev/null 2>&1')

    else:
        print('{"vit_status":98,"vit_message":"987"}')
        sys.exit(98)
if __name__ == '__main__':
    # st=time.time()
    main()
    # en=time.time()
    # print(en-st)
