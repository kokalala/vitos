import os
import sys
import json
from urllib.parse import unquote, urlencode, quote
import time, datetime
from concurrent.futures import ThreadPoolExecutor
import math

vit_prefix = "http://online.silentangel.audio/tidal?url="
app_song_info = '/mnt/mpd/app_song_info'
tidal_m3u8_path = "/tmp/vitos_tidal_list.m3u8"
quality_info='/mnt/settings/tidal_streaming_quality.conf'
airable_request='airable {}'


def check_data(data):
    try:
        data = json.loads(data)
        if data.get('description') == 'Please use your companion app to login':
            data['vit_status'] = 1
            data['vit_message'] = '101'
        else:
            data['vit_status'] = 0
            data['vit_message'] = ''
        return data
    except:
        return {'vit_status': 4, 'vit_message': '446'}



def tidal_parameter_dic(parameter):
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


def get_next_page_info(url, track_list):  # 递归获取所有的下一页歌曲
    url = "\"" + unquote(url) + "\""
    next_page_info = "".join(os.popen(airable_request.format(url)).readlines()).strip()
    next_page_info = check_data(data=next_page_info)

    if int(next_page_info.get('vit_status')) != 0:
        return next_page_info
    tracks = next_page_info.get('content', {}).get('entries', '')
    if tracks:
        track_list += tracks
    else:
        return track_list
    # 下一页链接.
    try:
        next_url = next_page_info.get('content').get('pagination').get('next')
    except:
        next_url = ''
    if not next_url:
        return track_list
    else:
        return get_next_page_info(url=next_url, track_list=track_list)


def threaing_get_tracks(url, page, track_dic,is_album=False):
    url += f"?p={page}"
    url = "\"" + unquote(url) + "\""
    current_page_info = "".join(os.popen(airable_request.format(url)).readlines()).strip()
    current_page_info = check_data(data=current_page_info)

    if page==1 and is_album==True:
        info_public = ''
        dict_album = {'title': 'Album', 'artist': 'Artist', 'release': 'Date'}
        for key in dict_album.keys():
            if key == 'title':
                value = current_page_info.get(key).replace('\n', '')
            elif key == 'artist':
                value = current_page_info.get(key).get('title').replace('\n', '')
            else:
                value = current_page_info.get(key)
                time_array = time.localtime(value)
                value = time.strftime("%Y-%m-%d", time_array)
            info_public += '{}: {}\n'.format(dict_album[key], value)
        image_large = current_page_info.get('images')[-1]
        if image_large:
            info_public += f"Cover: {image_large.get('url')}\n"
        image_small = current_page_info.get('images')[0]
        if image_small:
            info_public += f"CoverPreview: {image_small.get('url')}\n"
        tracks = current_page_info.get('content', {}).get('entries', [])
        track_dic[page] = tracks
        track_dic['info_public']=info_public
    else:
        tracks = current_page_info.get('content', {}).get('entries', [])
        track_dic[page] = tracks


def get_all_tracks(url, size, current, tracks_list=[],isalbum=False):

    url = "\"" + unquote(url) + "\""
    if not size:

        next_page_info = "".join(os.popen(airable_request.format(url)).readlines()).strip()
        next_page_info = check_data(data=next_page_info)

        if int(next_page_info.get('vit_status')) != 0:
            return next_page_info
        tracks = next_page_info.get('content', {}).get('entries', '')
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
        pages_value = next_page_info.get('content', {}).get('pagination', {}).get('pages', {}).get('values', [])
        current = next_page_info.get('content', {}).get('pagination', {}).get('pages', {}).get('current', '')
        current_index = pages_value.index(current)  # 当前页的index
        page1 = pages_value[current_index:]
        page2 = pages_value[:current_index]
        pages_value = page1 + page2
        pages_value.remove(current)
        track_dic = {}
        if pages_value:
            # 创建线程池
            threadPool = ThreadPoolExecutor(max_workers=6)
            for page in pages_value:
                threadPool.submit(threaing_get_tracks, url, page, track_dic, isalbum)
            threadPool.shutdown(wait=True)
            for k in pages_value:
                tracks_list += track_dic[k]
    else:
        size=int(size)
        page_list = [i for i in range(1, math.ceil(size / 20) + 1)]
        current_index = page_list.index(current)  # 当前页的index
        page1 = page_list[current_index:]
        page2 = page_list[:current_index]
        pages_value = page1 + page2

        track_dic = {}

        # 创建线程池
        threadPool = ThreadPoolExecutor(max_workers=6)
        for page in pages_value:
            threadPool.submit(threaing_get_tracks, url, page, track_dic,isalbum)
        threadPool.shutdown(wait=True)
        for k in pages_value:
            tracks_list += track_dic[k]
    if isalbum==False:
        return tracks_list
    else:
        return tracks_list,track_dic['info_public']


def get_100_tracks(url, track_list, is_favorite, is_next='next'):
    url = "\"" + unquote(url) + "\""
    next_page_info = "".join(os.popen(airable_request.format(url)).readlines()).strip()

    next_page_info = check_data(data=next_page_info)
    if int(next_page_info.get('vit_status')) != 0:
        return next_page_info

    tracks = next_page_info.get('content', {}).get('entries', '')
    current = next_page_info.get('content', {}).get('pagination', {}).get('pages').get('current')
    if int(current) == 1 and is_favorite == True:
        tracks = tracks[3:]

    if len(track_list) < 100:
        # 下一页链接.
        if is_next == 'next':
            if tracks:
                track_list += tracks
            else:
                return track_list
            next_url = quote(next_page_info.get('content', {}).get('pagination', {}).get('next', ''))

            if not next_url:
                return track_list
            else:
                return get_100_tracks(url=next_url, track_list=track_list, is_favorite=is_favorite)
        elif is_next == 'prev':
            if tracks:
                track_list = tracks + track_list
            else:
                return track_list
            prev_url = quote(next_page_info.get('content', {}).get('pagination', {}).get('prev', ''))
            if not prev_url:
                return track_list
            else:
                return get_100_tracks(url=prev_url, track_list=track_list, is_next='prev', is_favorite=is_favorite)
    else:
        return track_list


def tidal_get_play_url(parameter, quality='Master'):
    parameter_dic = tidal_parameter_dic(parameter)
    if isinstance(parameter_dic, str):
        return 'tidal_get_play_url 200'

    url = parameter_dic.get('track_id')
    if url:
        url = "\"" + unquote(url) + "\""
    else:
        return '{"vit_status":4,"vit_message":"403"}'

    data = "".join(os.popen(airable_request.format(url)).readlines()).strip()
    data = check_data(data=data)
    if data.get('vit_status') == 0:
        if data.get('description') == "Please use your companion app to login":
            return '{"vit_status":1,"vit_message":"100"}'  # 用户未登陆

        stream = data.get('streams')
        if not stream:
            return 'stream is None'
        if quality == 'Master':
            stream_url = stream[-1].get('url')
        elif quality == 'HiFi':
            i = 2
            while True:
                try:
                    stream_url = stream[i].get('url')
                    break
                except:
                    i -= 1
                    continue
        elif quality == 'High':
            try:
                stream_url = stream[1].get('url')
            except:
                stream_url = stream[0].get('url')
        elif quality == 'Normal':
            stream_url = stream[0].get('url')
        else:
            return '{"vit_status":4,"vit_message":"442"}'

        track_info = "".join(os.popen(airable_request.format(stream_url)).readlines()).strip()
        track_info = check_data(data=track_info)
        play_url = track_info.get('url')
        if play_url:
            return play_url
        else:
            return '{"vit_status":4,"vit_message":"441"}'  # 没有播放链接
    else:
        return data


def tidal_add_track(parameter, flag='a+'):
    if not parameter:
        return '200'
    key_list = ['Artist', 'Album', 'AlbumArtist', 'Title', 'Track', 'Genre', 'Date',
                'Cover', 'CoverPreview', 'Label', 'Composer', 'Time', 'duration', 'Format']
    track_id = ''
    model = 'insert'
    params = ''
    import urllib.parse
    for param in parameter.split('&'):
        if -1 == param.find('='):
            continue
        key = param.split('=', 1)[0]
        value = urllib.parse.unquote(param.split('=', 1)[1])
        if not value:
            continue
        if 'track_url' == key:
            track_uri = value
        elif 'model' == key:
            model = value
        elif key in key_list:
            params += '{}: {}\n'.format(key, value)
    if not track_uri or track_uri == '没有该字段':
        return '{"vit_status":4,"vit_message":"403"}'
    track_url = vit_prefix + track_uri

    info = 'song_begin: {}\n{}song_end\n'.format(track_url, params)

    info_dir = os.path.dirname(app_song_info)

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


def tidal_play_artist_tracks(parameter, type):
    parameter_dic = tidal_parameter_dic(parameter)
    if isinstance(parameter_dic, str):
        return '200'
    artist_track_url = parameter_dic.get('url')
    track_url = parameter_dic.get('track_url')
    current = parameter_dic.get('page')
    size = parameter_dic.get('size')

    if not artist_track_url:
        return '{"vit_status":2,"vit_message":"201"}'
    if not track_url or track_url == '没有该字段':
        return '{"vit_status":4,"vit_message":"403"}'
    if not current:
        return '{"vit_status":2,"vit_message":"203"}'
    else:
        current=int(current)
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
            artist_track_url_en = "\"" + artist_track_url + "?p={}" + "\""
            # 创建线程池
            threadPool = ThreadPoolExecutor(max_workers=6)
            track_dic = {}
            for i in pages[:5]:
                threadPool.submit(threaing_page_tracks, artist_track_url_en.format(i), i, track_dic)
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
        artist_track_url_st = "\"" + artist_track_url + f"?p={current}" + "\""
        artist_track_info = "".join(os.popen(airable_request.format(artist_track_url_st)).readlines()).strip()
        artist_track_info = check_data(data=artist_track_info)
        if int(artist_track_info.get('vit_status')) == 0:
            track_list = artist_track_info.get('content', {}).get('entries')
            sun = []
            for index, track in enumerate(track_list):  # 遍历当前页的track 如果没有返回歌曲的url则返回提示
                track_uri = track.get('url')
                if track_uri:
                    sun.append(track_uri)
            if not sun:
                print('{"vit_status":4,"vit_message":"403"}')
                sys.exit(403)
            page_list = artist_track_info.get('content', {}).get('pagination', {}).get('pages').get('values')  # 所有的页码
            current_index = page_list.index(current)  # 当前页的index
            page1 = page_list[current_index:]
            page2 = page_list[:current_index]
            pages = page1 + page2
            pages.remove(current)
            if pages:
                artist_track_url_p = "\"" + artist_track_url + "?p={}\""
                # 创建线程池
                threadPool = ThreadPoolExecutor(max_workers=6)
                track_dic = {}
                for i in pages[:4]:
                    threadPool.submit(threaing_page_tracks, artist_track_url_p.format(i), i, track_dic)
                threadPool.shutdown(wait=True)

                for k in pages[:4]:
                    track_list += track_dic[k]

    dict_track = {'title': 'Title', "artist": 'Artist', 'album': 'Album',
                  'release': 'Date', 'cover': 'CoverPreview', 'duration': 'Time'}

    info_public = ''
    info, track_all, play_index = append_song_info(dict_track, info_public, track_url, track_list)
    return save_song_info_and_play(info, artist_track_url, track_all, type=type)


def tidal_play_album(parameter, type):
    parameter_dic = tidal_parameter_dic(parameter)
    if isinstance(parameter_dic, str):
        return '200'
    album_url = parameter_dic.get('album_url')
    size =parameter_dic.get('size')
    if not album_url:
        return '{"vit_status":2,"vit_message":201}'
    track_url = parameter_dic.get('track_url')
    if not size:
        album_info = "".join(os.popen(airable_request.format(album_url)).readlines()).strip()
        album_info = check_data(data=album_info)
        if int(album_info.get('vit_status')) == 0:
            tracks = album_info.get('content').get('entries')
            # 遍历当前页歌曲 如果未找到播放链接则直接返回提示
            sun = []
            for index, track in enumerate(tracks):
                track_uri = track.get('url')
                if track_uri:
                    sun.append(track_uri)
            if not sun:
                print('{"vit_status":4,"vit_message":"403"}')
                sys.exit(403)

        current = album_info.get('content', {}).get('pagination', {}).get('pages').get('current')  # 当前页的页码
        page_list = album_info.get('content', {}).get('pagination', {}).get('pages').get('values') # 所有的页码

        current_index = page_list.index(current)  # 当前页的index
        page1 = page_list[current_index:]
        page2 = page_list[:current_index]
        pages = page1 + page2
        pages.remove(current)
        if pages:
            en_album_url=album_url+"?p={}"
            # 创建线程池
            threadPool = ThreadPoolExecutor(max_workers=6)
            track_dic = {}
            tracks = []
            for i in pages:
                threadPool.submit(threaing_page_tracks, en_album_url.format(i), i, track_dic,False)
            threadPool.shutdown(wait=True)
            for k in track_dic.keys():
                tracks += track_dic[k]
        info_public = ''
        dict_album = {'title': 'Album', 'artist': 'Artist', 'release': 'Date'}
        for key in dict_album.keys():
            if key == 'title':
                value = album_info.get(key).replace('\n', '')
            elif key == 'artist':
                value = album_info.get(key).get('title').replace('\n', '')
            else:
                value = album_info.get(key)
                time_array = time.localtime(value)
                value = time.strftime("%Y-%m-%d", time_array)
            info_public += '{}: {}\n'.format(dict_album[key], value)
        image_large = album_info.get('images')[-1]
        if image_large:
            info_public += f"Cover: {image_large.get('url')}\n"
        image_small = album_info.get('images')[0]
        if image_small:
            info_public += f"CoverPreview: {image_small.get('url')}\n"


    else:
        tracks, info_public = get_all_tracks(album_url, size, current=1, isalbum=True)
    dict_track = {"artist": 'Artist', 'title': 'Title', 'duration': 'Time', }

    info, track_all, play_index = append_song_info(dict_track, info_public, track_url, tracks)

    return save_song_info_and_play(info, album_url, track_all, type=type)



def tidal_play_playlist(parameter, type):
    parameter_dic = tidal_parameter_dic(parameter)
    if isinstance(parameter_dic, str):
        return '200'

    playlist_url = parameter_dic.get('playlist_url')
    size = parameter_dic.get('size')

    if not playlist_url:
        return '{"vit_status":2,"vit_message":201}'
    dict_track = {'title': 'Title', "artist": 'Artist', 'album': 'Album',
                  'release': 'Date', 'cover': 'CoverPreview', 'duration': 'Time'}
    info_public = ''

    track_url = parameter_dic.get('track_url')

    tracks = get_all_tracks(playlist_url, size, current=1)
    sun = []
    for index, track in enumerate(tracks[:20]):  # 遍历当前页的track 如果没有返回歌曲的url则返回提示
        track_uri = track.get('url')
        if track_uri:
            sun.append(track_uri)
    if not sun:
        print('{"vit_status":4,"vit_message":"403"}')
        sys.exit(403)

    info, track_all, play_index = append_song_info(dict_track, info_public, track_url, tracks)

    return save_song_info_and_play(info, playlist_url, track_all, type=type)


def threaing_page_tracks(url, page, track_dic, flag=False):
    for i in range(3):
        current_page_info = "".join(os.popen(airable_request.format(url)).readlines()).strip()
        current_page_info = check_data(data=current_page_info)
        if int(current_page_info.get('vit_status')) != 0:
            continue
        tracks = current_page_info.get('content', {}).get('entries', [])
        if page == int(1) and flag == True:
            track_dic[page] = tracks[3:]
        if tracks:
            track_dic[page] = tracks
            break

def tidal_play_my_track(parameter, type):
    parameter_dic = tidal_parameter_dic(parameter)
    if isinstance(parameter_dic, str):
        return '200'
    url = "\"" + 'https://meta.airable.io/tidal/my/tracks?p={}&s=a-z' + "\""
    track_url = parameter_dic.get('track_url', '')
    current = int(parameter_dic.get('page'))
    size = parameter_dic.get('size')
    if track_url == "" or track_url == "没有该字段":
        return '{"vit_status":4,"vit_message":"403"}'
    if not current:
        return '{"vit_status":2,"vit_message":"201"}'
    if not size:
        current_url = url.format(current)
        track_info = "".join(os.popen(airable_request.format(current_url)).readlines()).strip()
        track_info = check_data(track_info)
        if int(track_info.get('vit_status')) != 0:
            return track_info

        track_list = track_info.get('content').get('entries')

        sun = []
        for index, track in enumerate(track_list):  # 遍历当前页的track 如果没有返回歌曲的url则返回提示
            track_uri = track.get('url')
            if track_uri:
                sun.append(track_uri)
        if not sun:
            print('{"vit_status":4,"vit_message":"403"}')
            sys.exit(403)
        #
        if int(current) == 1:
            track_list = track_list[3:]
        page_list = track_info.get('content', {}).get('pagination', {}).get('pages').get('values')  # 所有的页码
        current_index = page_list.index(current)  # 当前页的index
        page1 = page_list[current_index:]
        page2 = page_list[:current_index]
        pages = page1 + page2
        pages.remove(current)
        # 创建线程池
        threadPool = ThreadPoolExecutor(max_workers=6)
        track_dic = {}
        for i in pages[:4]:
            threadPool.submit(threaing_page_tracks, url.format(i), i, track_dic, True)
        threadPool.shutdown(wait=True)

        for k in pages[:4]:
            track_list += track_dic[k]
    else:
        size=int(size)
        page_list = [i for i in range(1, math.ceil(size) + 1)]
        current_index = page_list.index(current)  # 当前页的index
        page1 = page_list[current_index:]
        page2 = page_list[:current_index]
        pages = page1 + page2
        if pages:
            track_list = []
            # 创建线程池
            threadPool = ThreadPoolExecutor(max_workers=6)
            track_dic = {}
            for i in pages[:5]:
                threadPool.submit(threaing_page_tracks, url.format(i), i, track_dic, True)
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
                        coverpreview = value[0]
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
            return save_song_info_and_play(info, track_url, track_all, type=type)
    except:
        return '{"vit_status":4,"vit_message":"886"}'


def tidal_play_hundred_tracks(parameter, url, type):
    parameter_dic = tidal_parameter_dic(parameter)
    if isinstance(parameter_dic, str):
        return '200'
    track_url = parameter_dic.get('track_url')
    size = parameter_dic.get('size')

    if not track_url or track_url == '没有该字段':
        return '{"vit_status":4,"vit_message":403}'
    current = parameter_dic.get('page', '1')
    if not current:
        return '{"vit_status":2,"vit_message":"202"}'
    else:
        current=int(current)
    if size:
        size=int(size)
        page_list = [i for i in range(1, math.ceil(size / 20) + 1)]
        tracks = []
        current_index = page_list.index(current)  # 当前页的index
        page1 = page_list[current_index:]
        page2 = page_list[:current_index]
        pages = page1 + page2
        if pages:
            # 创建线程池
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
        url1 = url.format(current)
        info = "".join(os.popen(airable_request.format(url1)).readlines()).strip()

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
                        coverpreview = value[0]
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


def tidal_play_seach_tracks(parameter, type):
    parameter_dic = tidal_parameter_dic(parameter)
    if isinstance(parameter_dic, str):
        return '200'
    track_url = parameter_dic.get('track_url', '')

    if track_url == "" or track_url == '没有该字段':
        return '{"vit_status":4,"vit_message":403}'
    query = parameter_dic.get('query').replace(' ','%20')
    current = parameter_dic.get('page')
    size = parameter_dic.get('size')
    if not query:
        return '{"vit_status":2,"vit_message":"201"}'
    if not current:
        return '{"vit_status":2,"vit_message":"203"}'
    else:
        current=int(current)
    # if not size:
    seach_url = "\""+f'https://meta.airable.io/tidal/search/tracks?q={query}&p={current}'+"\""
    seach_info = "".join(os.popen(airable_request.format(seach_url)).readlines()).strip()

    seach_info = check_data(seach_info)

    if int(seach_info.get('vit_status')) != 0:
        return seach_info

    tracks = seach_info.get('content').get('entries')

    sun = []
    for index, track in enumerate(tracks):  # 遍历当前页的track 如果没有返回歌曲的url则返回提示
        track_uri = track.get('url')
        if track_uri:
            sun.append(track_uri)
    if not sun:
        print('{"vit_status":4,"vit_message":"403"}')
        sys.exit(403)
    dict_track = {'title': 'Title', "artist": 'Artist', 'album': 'Album',
                      'release': 'Date', 'cover': 'CoverPreview', 'duration': 'Time'}
    info_public = ''
    info, track_all, play_index = append_song_info(dict_track, info_public, track_url, tracks)
        # page_list = seach_info.get('content', {}).get('pagination', {}).get('pages', {}).get('values')
        # current_index = page_list.index(current)
        # page1 = page_list[current_index:]
        # page2 = page_list[:current_index]
        # pages = page1 + page2
        # pages.remove(current)

        # if pages:
        #     创建线程池
            # threadPool = ThreadPoolExecutor(max_workers=6)
            # track_dic = {}
            # for i in pages[:4]:
            #     url = f'\"https://meta.airable.io/tidal/search/tracks?q={query}&p={i}\"'
            #     threadPool.submit(threaing_page_tracks, url, i, track_dic)
            # threadPool.shutdown(wait=True)

            # for k in pages[:4]:
            #     tracks += track_dic[k]
    # else:
    #     size=int(size)
    #     page_list = [i for i in range(1, math.ceil(size / 20) + 1)]
    #     current_index = page_list.index(current)
    #     page1 = page_list[current_index:]
    #     page2 = page_list[:current_index]
    #     pages = page1 + page2
    #     if pages:
    #         tracks = []
    #         threadPool = ThreadPoolExecutor(max_workers=6)
    #         track_dic = {}
    #         for i in pages[:5]:
    #             url = f'\"https://meta.airable.io/tidal/search/tracks?q={query}&p={i}\"'
    #             threadPool.submit(threaing_page_tracks, url, i, track_dic)
    #         threadPool.shutdown(wait=True)
    #         for k in pages[:5]:
    #             tracks += track_dic[k]
    #         sun = []
    #         for index, track in enumerate(tracks[:20]):  # 遍历当前页的track 如果没有返回歌曲的url则返回提示
    #             track_uri = track.get('url')
    #             if track_uri:
    #                 sun.append(track_uri)
    #         if not sun:
    #             print('{"vit_status":4,"vit_message":"403"}')
    #             sys.exit(403)


    # info_public = ''
    # info, track_all, play_index = append_song_info(dict_track, info_public, track_url, tracks)

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
                        coverpreview = value[0]
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


def append_song_info(dic_track, info_public, song_url, tracks):
    play_index = -1
    info = ''
    track_all = []
    for index, track in enumerate(tracks):

        track_uri = track.get('url')
        if not track_uri:
            continue
        if str(song_url) == str(track_uri):
            play_index = index

        track_url = f"{vit_prefix}{track_uri}\n"

        if -1 == play_index:
            track_all.append(track_url)
        else:
            track_all.insert(index - play_index, track_url)

        info += 'song_begin: {}'.format(track_url)
        for key in dic_track.keys():

            if key == 'artist' or key == 'album':
                value = track.get(key, {}).get('title', '').replace('\n', '')
            elif key == 'release':
                value = track.get('album',    {}).get('release')
                if not value:
                    continue
                else:
                    time_array = time.localtime(value)
                    value = time.strftime("%Y-%m-%d", time_array)
                    info += '{}: {}\n'.format(dic_track[key], value)
                    continue
            elif key == 'cover':
                value = track.get('images')
                if value:
                    cover = value[-1].get('url')

                    coverpreview = value[0].get('url')

                    info += f'Cover: {cover}\nCoverPreview: {coverpreview}\n'
                    continue
                else:
                    continue

            else:
                value = str(track.get(key)).replace('\n', '')
            if not value:
                continue
            mpd_key = dic_track[key]
            if key == 'duration':
                info += f'duration: {value}\n'
            info += f'{mpd_key}: {value}\n'
        info += info_public + 'song_end\n'
    return info, track_all, play_index


def save_song_info_and_play(info, url, track_all, type):
    info_dir = os.path.dirname(app_song_info)
    if not os.path.exists(info_dir):
        os.makedirs(info_dir)
    with open(app_song_info, type, encoding='utf8')as f:
        f.write(info)

    with open(tidal_m3u8_path, mode='w+', encoding='utf8')as f3:
        f3.write(''.join(track_all))
    if type == 'w+':
        # 修改开始播放默认第一首歌 也就是客户端选中的那首歌 这样才不会在随机播放的模式下无法播放客户端选中的歌曲
        os.system( 'mpc clear > /dev/null 2>&1 && mpc load {}  > /dev/null 2>&1 && mpc play 1 > /dev/null 2>&1'.format(
                tidal_m3u8_path))
    elif type == 'a+':
        os.system('mpc load {}  > /dev/null 2>&1'.format(tidal_m3u8_path))
    return '{"vit_status":0,"vit_message":"' + url.replace("\"", '') + '"}'


def tidal_login_and_quality():
    url = 'https://meta.airable.io/tidal/new/playlists'
    data = "".join(os.popen(airable_request.format(url)).readlines()).strip()
    try:
        data = json.loads(data)
        if data.get('description') == 'Please use your companion app to login':
            login = False
            login_url = data.get('buttons')[1].get('url')
        else:
            login = True
            login_url = ''
    except:
        return json.dumps({'vit_status': 4, 'vit_message': '446'})
    try:
        with open(quality_info) as f:
            quality = f.read()
        if not quality:
            quality = 'Master'
    except:
        quality = 'Master'
    return json.dumps({"vit_status": 0, 'vit_message': "", 'login': login, 'quality': quality, 'login_url': login_url})


def tidal_logout():
    logout_url = 'https://meta.airable.io/tidal/logout'
    info = ''
    skip_tidal = False
    try:
        os.system('mpc playlistdel http://online.silentangel.audio/tidal > /dev/null 2>&1')
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
    os.popen('find /mnt/streaming_cache/title/ -type f -mtime -1 -name "*" -exec rm -rf {} \; > /dev/null 2>&1')
    return data


def quality_set(quality):
    quality_list = ['Master', 'HiFi', 'High', 'Normal']
    if quality not in quality_list:
        quality = "Master"
    try:
        with open(quality_info, 'w+', encoding='utf8') as f:
            f.write(quality)
        return json.dumps({'vit_status': 0, 'vit_message': ''})
    except:
        return json.dumps({'vit_status': 4, 'vit_message': '444'})






def main():
    try:
        tidal_paramter = sys.argv[2]

    except:
        tidal_paramter = ''

    try:
        tidal_manage = sys.argv[1]
    except:
        tidal_manage = ''

    if tidal_manage == 'index':

        url = "https://meta.airable.io/tidal"
        data = "".join(os.popen(airable_request.format(url)).readlines()).strip()
        data = check_data(data)
        if data.get('vit_status') != 0:
            print(json.dumps(data))
            sys.exit(101)
        else:
            print(json.dumps(data))
    elif tidal_manage == 'quality_set':
        parameter_dic = tidal_parameter_dic(tidal_paramter)
        quality = parameter_dic.get('quality')
        print(quality_set(quality))
        sys.exit(0)
    elif tidal_manage == 'login_and_quality':
        print(tidal_login_and_quality())
    # ---------------------------------------------------new-----------------------------------------------------------------
    elif tidal_manage == 'new_playlist':
        url = 'https://meta.airable.io/tidal/new/playlists'
        data = "".join(os.popen(airable_request.format(url)).readlines()).strip()
        data = check_data(data)
        print(json.dumps(data))
    elif tidal_manage == 'new_album':
        url = 'https://meta.airable.io/tidal/new/albums'
        data = "".join(os.popen(airable_request.format(url)).readlines()).strip()
        data = check_data(data)
        print(json.dumps(data))
    elif tidal_manage == 'new_track':
        url = 'https://meta.airable.io/tidal/new/tracks'
        data = "".join(os.popen(airable_request.format(url)).readlines()).strip()
        data = check_data(data)

        print(json.dumps(data))
    # ---------------------------------------------------TIDAL Rising-------------------------------------------------------
    elif tidal_manage == 'rising_album':
        url = 'https://meta.airable.io/tidal/rising/albums'
        data = "".join(os.popen(airable_request.format(url)).readlines()).strip()
        data = check_data(data)
        print(json.dumps(data))
    elif tidal_manage == 'rising_track':
        url = 'https://meta.airable.io/tidal/rising/tracks'
        data = "".join(os.popen(airable_request.format(url)).readlines()).strip()
        data = check_data(data)
        print(json.dumps(data))

        # ------------------------------------------------- TIDAL Masters----------------------------------------
    elif tidal_manage == 'master_album':
        url = 'https://meta.airable.io/tidal/master/albums'
        data = "".join(os.popen(airable_request.format(url)).readlines()).strip()
        data = check_data(data)
        print(json.dumps(data))
    elif tidal_manage == 'master_playlist':
        url = 'https://meta.airable.io/tidal/master/playlists'
        data = "".join(os.popen(airable_request.format(url)).readlines()).strip()
        data = check_data(data)
        print(json.dumps(data))

    # ------------------------------------------------- Playlists-------------------------------------------
    elif tidal_manage == 'by_mood':
        url = 'https://meta.airable.io/tidal/playlists/moods'
        data = "".join(os.popen(airable_request.format(url)).readlines()).strip()
        data = check_data(data)
        print(json.dumps(data))

    elif tidal_manage == 'playlist_new':
        url = 'https://meta.airable.io/tidal/playlists/new'
        data = "".join(os.popen(airable_request.format(url)).readlines()).strip()
        data = check_data(data)
        print(json.dumps(data))


    elif tidal_manage == 'recommended_playlist':
        url = 'https://meta.airable.io/tidal/playlists/recommended'
        data = "".join(os.popen(airable_request.format(url)).readlines()).strip()
        data = check_data(data)

        print(json.dumps(data))

    # ------------------------------------------------ Genres---------------------------------------------------------------
    elif tidal_manage == 'genres':
        url = 'https://meta.airable.io/tidal/genres'
        data = "".join(os.popen(airable_request.format(url)).readlines()).strip()
        data = check_data(data)
        print(json.dumps(data))
    # ----------------------------------------------My Music----------------------------------------------------------------
    elif tidal_manage == 'my_playlists':
        url = 'https://meta.airable.io/tidal/my/playlists?s=a-z'
        data = "".join(os.popen(airable_request.format(url)).readlines()).strip()
        data = check_data(data)
        print(json.dumps(data))

    elif tidal_manage == 'my_albums':
        url = 'https://meta.airable.io/tidal/my/albums?s=a-z'
        data = "".join(os.popen(airable_request.format(url)).readlines()).strip()
        data = check_data(data)
        print(json.dumps(data))
    elif tidal_manage == 'my_tracks':
        url = 'https://meta.airable.io/tidal/my/tracks?s=a-z'
        data = "".join(os.popen(airable_request.format(url)).readlines()).strip()
        data = check_data(data)
        print(json.dumps(data))
    elif tidal_manage == 'my_artists':
        url = 'https://meta.airable.io/tidal/my/artists?s=a-z'
        data = "".join(os.popen(airable_request.format(url)).readlines()).strip()
        data = check_data(data)
        print(json.dumps(data))
    # ----------------------------------------------播放列表相关操作------------------------------------------------------------
    elif tidal_manage == 'insert_new_playlist':
        parameter_dic = tidal_parameter_dic(tidal_paramter)
        track_id = parameter_dic.get('track_id')
        if not track_id:
            print(json.dumps({'vit_status': 2, 'vit_message': '201'}))
            sys.exit(201)
        playlist_name = parameter_dic.get('playlist_name')
        if not playlist_name:
            print(json.dumps({'vit_status': 2, 'vit_message': '202'}))
            sys.exit(202)
        url = f"https://meta.airable.io/actions/tidal/track/{track_id}/playlist/new/insert?name={playlist_name}"
        data = "".join(os.popen(airable_request.format(url)).readlines()).strip()
        data = check_data(data)
        print(json.dumps(data))
    elif tidal_manage == 'insert_playlist':
        parameter_dic = tidal_parameter_dic(tidal_paramter)
        playlist_id = parameter_dic.get('id')
        track_id = parameter_dic.get('track_id')
        url = f'https://meta.airable.io/actions/tidal/track/{track_id}/playlist/{playlist_id}/insert'
        data = "".join(os.popen(airable_request.format(url)).readlines()).strip()
        data = check_data(data)
        print(json.dumps(data))

    # ------------------------------------------------搜索-------------------------------------------------------------------
    elif tidal_manage == 'seach_albums':
        parameter_dic = tidal_parameter_dic(tidal_paramter)
        query = parameter_dic.get('query').replace(' ','%20')
        if not query:
            print(json.dumps({'vit_status': 1, 'vit_message': '201'}))
            sys.exit(201)
        url = f'https://meta.airable.io/tidal/search/albums?q={query}'
        data = "".join(os.popen(airable_request.format(url)).readlines()).strip()
        data = check_data(data)
        print(json.dumps(data))
    elif tidal_manage == 'seach_playlists':
        parameter_dic = tidal_parameter_dic(tidal_paramter)
        query = parameter_dic.get('query').replace(' ','%20')
        if not query:
            print(json.dumps({'vit_status': 1, 'vit_message': '201'}))
            sys.exit(201)
        url = f'https://meta.airable.io/tidal/search/playlists?q={query}'
        data = "".join(os.popen(airable_request.format(url)).readlines()).strip()
        data = check_data(data)
        print(json.dumps(data))

    elif tidal_manage == 'seach_tracks':
        parameter_dic = tidal_parameter_dic(tidal_paramter)
        query = parameter_dic.get('query').replace(' ',"%20")
        if not query:
            print(json.dumps({'vit_status': 1, 'vit_message': '201'}))
            sys.exit(201)
        url = f'https://meta.airable.io/tidal/search/tracks?q={query}'
        data = "".join(os.popen(airable_request.format(url)).readlines()).strip()
        data = check_data(data)
        print(json.dumps(data))
    elif tidal_manage == 'seach_artists':
        parameter_dic = tidal_parameter_dic(tidal_paramter)
        query = parameter_dic.get('query').replace(' ','%20')
        if not query:
            print(json.dumps({'vit_status': 1, 'vit_message': '201'}))
            sys.exit(201)
        url = f'https://meta.airable.io/tidal/search/artists?q={query}'
        data = "".join(os.popen(airable_request.format(url)).readlines()).strip()
        data = check_data(data)
        print(json.dumps(data))
    elif tidal_manage == "common":
        parameter_dic = tidal_parameter_dic(tidal_paramter)
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
    # ------------------------------------------------登出-------------------------------------------------------------------
    elif tidal_manage == 'logout':
        print(tidal_logout())
    # -----------------------------------------------播放-------------------------------------------------------------------
    elif tidal_manage == 'track_url':

        try:
            with open(quality_info) as f:
                quality = f.read()
            if not quality:
                quality = 'Master'
        except:
            quality = 'Master'

        url = tidal_get_play_url(tidal_paramter, quality=quality)
        print(url)
    elif tidal_manage == 'add_track':
        print(tidal_add_track(parameter=tidal_paramter))
    elif tidal_manage == 'play_album':
        print(tidal_play_album(parameter=tidal_paramter, type='w+'))
    elif tidal_manage == 'play_playlist':
        print(tidal_play_playlist(parameter=tidal_paramter, type='w+'))
    elif tidal_manage == 'play_my_track':
        print(tidal_play_my_track(parameter=tidal_paramter, type='w+'))
    elif tidal_manage == 'playlist_add_album':
        print(tidal_play_album(parameter=tidal_paramter, type='a+'))
    elif tidal_manage == 'playlist_add_playlist':
        print(tidal_play_playlist(parameter=tidal_paramter, type='a+'))
    elif tidal_manage == 'play_seach_track':
        print(tidal_play_seach_tracks(parameter=tidal_paramter, type='w+'))
    elif tidal_manage == 'add_seach_track':
        print(tidal_play_seach_tracks(parameter=tidal_paramter, type='a+'))
    elif tidal_manage == 'play_artist_track':
        print(tidal_play_artist_tracks(parameter=tidal_paramter, type='w+'))
    elif tidal_manage == 'add_artist_track':
        print(tidal_play_artist_tracks(parameter=tidal_paramter, type='a+'))
    elif tidal_manage == 'play_new_tracks':
        url = '\"https://meta.airable.io/tidal/new/tracks?p={}\"'
        print(tidal_play_hundred_tracks(parameter=tidal_paramter, url=url, type='w+'))
    elif tidal_manage == 'play_rising_tracks':
        url = "https://meta.airable.io/tidal/rising/tracks?p={}"
        print(tidal_play_hundred_tracks(parameter=tidal_paramter, url=url, type='w+'))
    elif tidal_manage == 'play_top_tracks':
        parameter_dic = tidal_parameter_dic(tidal_paramter)
        url = parameter_dic.get('url')
        if not url:
            print('{"vit_status":2,"vit_message":"203"}')
            sys.exit(203)
        else:
            url = url + '?p={}'
            print(tidal_play_hundred_tracks(parameter=tidal_paramter, url=url, type="w+"))


    else:
        print('{"vit_status":98,"vit_message":"987"}')
        sys.exit(98)


if __name__ == '__main__':
    # st = time.time()
    main()
    # en = time.time()
    # print(en - st)
