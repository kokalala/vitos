# *encoding=utf-8

# Created by wannoo on 2021/7/25.
# Copyright © 2021 Thunder Data Co. Ltd. All rights reserved.
#############################################################

import json
import os
import sys
import hra_streaming_api as hra

app_song_info = '/mnt/mpd/app_song_info'
hra_m3u8_path = "/tmp/vitos_hra_list.m3u8"
vit_prefix = "http://online.silentangel.audio/hra/"


# 通过歌曲ID获取播放链接，这个是”/bin/m1-app-uri-id“在调用
def hra_get_url_by_id(parameter):
    try:
        params_dic = hra.hra_params_dic(parameter)
        if isinstance(params_dic, str):
            return json.loads(params_dic).get('vit_message')
        track_id = params_dic.get('track_id')
        url = ''
        track_title = None
        is_favorite = False

        track_str = hra.single_track_or_album(params_dic)
        track_json = json.loads(track_str)
        vit_status = track_json.get('vit_status')
        if 0 == vit_status:
            tracks = track_json.get('data').get('results').get('tracks')
            url = tracks.get('url')
            if url is not None and url and 0 != len(url.strip()):
                return url
            track_title = tracks.get('title')
            is_favorite = tracks.get('is_favorite')
        else:
            vit_message = track_json.get('vit_message')
            if '444' != vit_message:
                return vit_message

        if track_title is None:
            if -1 != track_id.find('_'):
                album_id = track_id.split('_', 1)[1]
                album_details = hra.album_details(hra.hra_params_dic(f'album_id={album_id}'))
                tracks = json.loads(album_details).get('data').get('results').get('tracks')
                for track in tracks:  # 从专辑详细里获取歌曲的url
                    if track_id == track.get('playlistAdd'):
                        url = track.get('url')
                        if url is not None and url and 0 != len(url.strip()):
                            return url
                        track_title = track.get('title')
                        is_favorite = track.get('is_favorite')
                        break

        if not is_favorite or 'false' == is_favorite.lower():  # 将歌曲收藏
            hra.add_single_track_to_my_track_list(hra.hra_params_dic(f'id={track_id}'))

        param = f'title={track_title}&limit=1000' if not track_title and track_title is not None else "limit=1000"
        track_list = hra.my_track_list(hra.hra_params_dic(param))
        tracks = json.loads(track_list).get('data').get('data').get('results')
        for track in tracks:  # 从收藏的歌曲里获取url
            if track_id == track.get('playlistAdd'):
                url = track.get('url')
                break

        if not is_favorite or 'false' == is_favorite.lower():  # 将歌曲取消收藏
            hra.delete_single_track_from_my_track_list(hra.hra_params_dic(f'id={track_id}'))

        return url
    except Exception:
        return '555'


# 通过歌曲ID获取歌曲的图片
def hra_get_cover_by_id(parameter):
    try:
        album_id = None
        parameter_list = parameter.split('&')
        for parameter in parameter_list:
            if -1 != parameter.find('='):
                params = parameter.split('=', 1)
                if 'track_id' == params[0] and -1 != params[1].find('_'):
                    album_id = params[1].split('_', 1)[1]
        if album_id is None or not album_id or 0 == len(album_id.strip()):
            return '{"vit_status":2,"vit_message":"201"}'
        try:
            import requests
            for i in range(10):
                try:
                    response = requests.get(hra.base_url + '/vault/album/', params={'album_id': album_id}, verify=False,
                                            timeout=58)
                    break
                except requests.exceptions.SSLError:
                    return '{"vit_status":4,"vit_message":"579"}'
                except requests.exceptions.ConnectTimeout:  # 连接超时
                    return '{"vit_status":4,"vit_message":"578"}'
                except requests.exceptions.ConnectionError:
                    if 9 == i:
                        return False, '{"vit_status":4,"vit_message":"577"}'
                    else:
                        continue
            if response.status_code != 200:
                return '{"vit_status":4,"vit_message":"' + str(response.status_code) + '"}'  # 请求错误
        except Exception:  # 连接错误
            return '{"vit_status":4,"vit_message":"443"}'

        track_json = json.loads(response.text)
        cover = track_json.get('data').get('results').get('cover')
        cover_master = cover.get('master').get('file_url')
        if cover_master and not cover_master.startswith('http://') and not cover_master.startswith('https://'):
            cover_master = 'https://' + cover_master
        cover_preview = cover.get('preview').get('file_url')
        if cover_preview and not cover_preview.startswith('http://') and not cover_preview.startswith('https://'):
            cover_preview = 'https://' + cover_preview
        cover_thumbnail = cover.get('master').get('thumbnail')
        if cover_thumbnail and not cover_thumbnail.startswith('http://') and not cover_thumbnail.startswith('https://'):
            cover_thumbnail = 'https://' + cover_thumbnail
        return json.dumps({"vit_status": 0, "vit_message": album_id, "cover_master": cover_master,
                           "cover_preview": cover_preview, "cover_thumbnail": cover_thumbnail})
    except Exception:
        return '{"vit_status":4,"vit_message":"449"}'


def hra_add_track(parameter):
    if not os.path.exists(hra.info_path):
        return '{"vit_status":1,"vit_message":"101"}'
    if not parameter:
        return '{"vit_status":2,"vit_message":"201"}'

    key_list = ['Artist', 'Album', 'AlbumArtist', 'Title', 'Track', 'Genre', 'Date', 'Cover', 'CoverPreview', 'Label',
                'Composer', 'Time', 'duration', 'Format']
    # 'Composer', 'Time', 'duration', 'Format', 'Source']
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
        if 'track_id' == key:
            track_id = value
        elif 'model' == key:
            model = value
        elif key in key_list:
            if key=='Date':
                try:
                    value=value.split('T')[0]
                except:
                    pass
            elif 'Format' == key:
                try:
                    if float(value) > 384:
                        byt = int(float(value) * 100)
                    else:
                        byt = int(float(value) * 1000)
                    value = f'{byt}:*:*'
                except ValueError:
                    pass
            params += '{}: {}\n'.format(key, value)
    if not track_id:
        return '{"vit_status":2,"vit_message":"202"}'

    track_url = vit_prefix + track_id
    info = 'song_begin: {}\n{}song_end\n'.format(track_url, params)

    info_dir = os.path.dirname(app_song_info)
    if not os.path.exists(info_dir):
        os.makedirs(info_dir)
    with open(app_song_info, 'a+', encoding='utf8') as f:
        f.write(info)
    if 'insert' == model:
        os.system('mpc insert {}  > /dev/null 2>&1'.format(track_url))
    else:
        os.system('mpc add {}  > /dev/null 2>&1'.format(track_url))
    return '{"vit_status":0,"vit_message":"' + track_id + '"}'


def hra_play_album(parameter):
    params_dic = hra.hra_params_dic(parameter)
    if isinstance(params_dic, str):
        return params_dic
    album_id = params_dic.get('album_id')
    track_id = params_dic.get('track_id')
    try:
        track_str = hra.album_details(params_dic)
        data = json.loads(track_str).get('data')
        results = data.get('results')
        tracks = results.get('tracks')
    except Exception:
        return '{"vit_status":4,"vit_message":"888"}'

    dict_album = {'title': 'Album', 'artist': 'AlbumArtist', 'genre': 'Genre', 'releaseDate': 'Date', 'label': 'Label',
                  'composer': 'Composer'}
    info_public = ''
    # info_public = 'Source: album {}\n'.format(album_id)
    for key in dict_album.keys():
        if key=='releaseDate':
            value = results.get(key)
            try:
                value = value.split('T')[0]
            except:
                value=""
        else:
            value = results.get(key)

        if value:
            info_public += '{}: {}\n'.format(dict_album[key], value)
    cover = results.get('cover')  # cover Cover
    if cover is not None and cover:
        cover_master = cover.get('master').get('file_url')
        cover_preview = cover.get('preview').get('file_url')
        if cover_master:
            info_public += '{}: {}\n'.format('Cover', cover_master)
        if cover_preview:
            info_public += '{}: {}\n'.format('CoverPreview' if cover_master else 'Cover', cover_preview)

    dict_track = {"artist": 'Artist', 'title': 'Title', 'trackNumber': 'Track', 'playtime': 'Time',
                  'format': 'Format'}
    info, track_all, play_index = append_song_info(dict_track, info_public, track_id, tracks)
    return save_song_info_and_play(info, album_id, track_all)


def hra_play_playlist(parameter):
    params_dic = hra.hra_params_dic(parameter)
    if isinstance(params_dic, str):
        return params_dic
    playlist_id = params_dic.get('playlist_id')
    track_id = params_dic.get('track_id')
    params_dic['id'] = playlist_id
    try:
        track_str = hra.details_of_an_editorial_playlist(params_dic)
        data = json.loads(track_str).get('data')
        tracks = data.get('results')[0].get('tracks')
    except Exception:
        return '{"vit_status":4,"vit_message":"888"}'

    dict_track = {'title': 'Title', "artist": 'Artist', 'album': 'Album', 'cover': 'CoverPreview', 'format': 'Format',
                  'playtime': 'Time'}
    info_public = ''
    # info_public = 'Source: playlist {}\n'.format(playlist_id)
    info, track_all, play_index = append_song_info(dict_track, info_public, track_id, tracks)
    return save_song_info_and_play(info, playlist_id, track_all)


def hra_play_my_playlist(parameter):
    params_dic = hra.hra_params_dic(parameter)
    if isinstance(params_dic, str):
        return params_dic
    playlist_id = params_dic.get('playlist_id')
    track_id = params_dic.get('track_id')
    try:
        track_str = hra.get_single_user_playlist(params_dic)
        tracks = json.loads(track_str).get('data').get('data')
    except Exception:
        return '{"vit_status":4,"vit_message":"888"}'

    dict_track = {'title': 'Title', "artist": 'Artist', 'label': 'Label', 'trackNumber': 'Track', 'genre': 'Genre',
                  'album_title': 'Album', 'cover': 'CoverPreview', 'format': 'Format', 'playtime': 'Time'}
    info_public = ''
    # info_public = 'Source: my_playlist {}\n'.format(playlist_id)
    info, track_all, play_index = append_song_info(dict_track, info_public, track_id, tracks)
    return save_song_info_and_play(info, playlist_id, track_all)


def hra_play_my_track(parameter):
    params_dic = hra.hra_params_dic(parameter)
    if isinstance(params_dic, str):
        return params_dic
    track_id = params_dic.get('track_id')
    index = params_dic.get('track_index')
    if not index or not index.isdigit():
        index = 0
    params_dic['offset'] = index
    params_dic['limit'] = 100
    try:
        track_str = hra.my_track_list(params_dic)
        tracks = json.loads(track_str).get('data').get('data').get('results')
    except Exception:
        return '{"vit_status":4,"vit_message":"888"}'

    dict_track = {'title': 'Title', "artist": 'Artist', 'label': 'Label', 'trackNumber': 'Track', 'genre': 'Genre',
                  'album': 'Album', 'cover': 'CoverUncertainty', 'format': 'Format', 'playtime': 'Time',
                  'releaseDate': 'Date', 'composer': 'Composer'}
    info_public = ''
    # info_public = 'Source: my_track \n'
    info, track_all, play_index = append_song_info(dict_track, info_public, track_id, tracks)

    if -1 != play_index:
        return save_song_info_and_play(info, track_id, track_all)

    try:
        params_dic_new = {'track_id': track_id}
        track_str = hra.single_track_or_album(params_dic_new)
        track_json = json.loads(track_str)
        vit_status = track_json.get('vit_status')
        if 0 == vit_status:
            track = track_json.get('data').get('results').get('tracks')
            playlist_add = track.get('playlistAdd')
            if playlist_add:
                track_url = '{}{}\n'.format(vit_prefix, playlist_add)
                track_all.insert(0, track_url)
                info += 'song_begin: {}'.format(track_url)
                dict_track = {'title': 'Title', "artist": 'Artist', 'trackNumber': 'Track', 'album_title': 'Album',
                              'cover': 'Cover', 'format': 'Format', 'playtime': 'Time'}
                for key in dict_track.keys():
                    value = track.get(key)
                    if not value:
                        continue
                    if 'playtime' == key:
                        info += 'duration: {}\n'.format(value)
                    elif 'format' == key:
                        try:
                            if float(value) > 384:
                                byt = int(float(value) * 100)
                            else:
                                byt = int(float(value) * 1000)
                            value = f'{byt}:*:*'
                        except ValueError:
                            pass
                    info += '{}: {}\n'.format(dict_track[key], value)
                info += 'song_end\n'
                return save_song_info_and_play(info, track_id, track_all)
    except Exception:
        pass
    return '{"vit_status":4,"vit_message":"886"}'


# 遍历列表将获取需要的信息
def append_song_info(dict_track, info_public, track_id, tracks):
    play_index = -1
    info = ''
    track_all = []
    for index, track in enumerate(tracks):
        playlist_add = track.get('playlistAdd')
        if not playlist_add:
            continue
        if track_id == playlist_add:
            play_index = index
        track_url = '{}{}\n'.format(vit_prefix, playlist_add)
        if -1 == play_index:
            track_all.append(track_url)
        else:
            track_all.insert(index - play_index, track_url)
        info += 'song_begin: {}'.format(track_url)
        for key in dict_track.keys():
            value = track.get(key)

            if not value:
                continue
            mpd_key = dict_track[key]
            if key == 'releaseDate':
                value = track.get(key)
                try:
                    value = value.split('T')[0]
                except:
                    pass
            elif 'playtime' == key:
                info += 'duration: {}\n'.format(value)
            elif 'cover' == key and 'CoverUncertainty' == mpd_key:
                if value.endswith('-master.jpg'):
                    mpd_key = 'Cover'
                else:
                    mpd_key = 'CoverPreview'
            elif 'format' == key:
                try:
                    if float(value) > 384:
                        byt = int(float(value) * 100)
                    else:
                        byt = int(float(value) * 1000)
                    value = f'{byt}:*:*'
                except ValueError:
                    pass
            info += '{}: {}\n'.format(mpd_key, value)
        info += info_public + 'song_end\n'
    return info, track_all, play_index


# 将歌曲信息存储起来，然后调用mpd的播放功能
def save_song_info_and_play(info, playlist_id, track_all):
    info_dir = os.path.dirname(app_song_info)
    if not os.path.exists(info_dir):
        os.makedirs(info_dir)
    f = open(app_song_info, 'a+', encoding='utf8')
    f.truncate(0)
    f.write(info)
    f.close()
    with open(hra_m3u8_path, 'w+', encoding='utf8') as f3:
        f3.write(''.join(track_all))
    os.system('mpc clear > /dev/null 2>&1 && mpc load {}  > /dev/null 2>&1 && mpc play 1 > /dev/null 2>&1'.format(
        hra_m3u8_path))
    return '{"vit_status":0,"vit_message":"' + playlist_id + '"}'


def main():
    try:
        hra_manage = sys.argv[1]
    except IndexError:
        print('{"vit_status":98,"vit_message":"986"}')
        sys.exit(98)
    try:
        hra_parameter = sys.argv[2]
    except IndexError:
        hra_parameter = ''

    if hra_manage == 'track_url':  # 获取歌曲链接
        print(hra_get_url_by_id(parameter=hra_parameter))
    elif hra_manage == "get_cover":  # 获取歌曲图片
        print(hra_get_cover_by_id(parameter=hra_parameter))
    elif hra_manage == "add_track":  # 下一首播放；加到播放队列
        print(hra_add_track(parameter=hra_parameter))
    elif hra_manage == 'play_album':  # 播放专辑
        print(hra_play_album(parameter=hra_parameter))
    elif hra_manage == 'play_playlist':  # 播放歌单
        print(hra_play_playlist(parameter=hra_parameter))
    elif hra_manage == 'play_my_playlist':  # 播放我的歌单
        print(hra_play_my_playlist(parameter=hra_parameter))
    elif hra_manage == 'play_my_track':  # 播放我的歌曲
        print(hra_play_my_track(parameter=hra_parameter))
    else:
        print('{"vit_status":98,"vit_message":"987"}')
        sys.exit(98)


if __name__ == '__main__':
    main()
