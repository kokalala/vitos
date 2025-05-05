import json
import os
import sys
import raw

app_song_info = '/mnt/mpd/app_song_info'
qobuz_m3u8_path = "/tmp/vitos_qobuz_list.m3u8"
vit_prefix = "http://online.silentangel.audio/qobuz/"


def initialize_api():
    global api
    api = raw.RawApi("950096963", "")
    vit_status=json.loads(api.td_qobuz_maybe_login())
    return vit_status


def qobuz_get_url_by_id(parameter):
    params_dic = api.td_qobuz_parameter_dic(parameter)
    if isinstance(params_dic, str):
        return '200'
    track_id = params_dic.get('track_id')
    track_info=api.td_qobuz_track_getFileUrl(parameter=f'track_id={track_id}')
    if track_info.get('vit_status')==0:
        play_url=track_info.get('url')
        if play_url:
            return play_url
        else:
            return '{"vit_status":4,"vit_message":"441"}'#没有播放链接
    else:
        # vit_message = track_info.get('vit_message')
        return json.dumps(track_info)



def qobuz_next_track(parameter,flag='a+'):
    if not os.path.exists(raw.info_path):
        return '{"vit_status":1,"vit_message":"101"}'
    if not parameter:
        return '{"vit_status":2,"vit_message":"201"}'
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
        if 'track_id'==key:
            track_id=value
        elif 'model'==key:
            model=value
        elif key in key_list:
            params += '{}: {}\n'.format(key, value)
    if not track_id:
        return '{"vit_status":2,"vit_message":"202"}'
    track_url=vit_prefix+track_id

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


def qobuz_play_album(parameter,type):#parameter 一般包含album_id和track_id 至少包含album_id
    parameter_dic = api.td_qobuz_parameter_dic(parameter)
    if parameter:
        album_id = parameter_dic.get('album_id')
        track_id = parameter_dic.get('track_id')

    else:
        return parameter

    try:
        album_info=api.td_qobuz_album_get(parameter=f'album_id={album_id}')
        if album_info.get('vit_status')==0:
            tracks= album_info.get('tracks').get('items')
        else:
            return album_info
    except:
        return '{"vit_status":4,"vit_message":"888"}'
    info_public = ''

    dict_album = {'title': 'Album', 'artists': 'Artist', 'genre': 'Genre',
                  'release_date_original': 'Date', 'label': 'Label','composer': 'Composer'}
    for key in dict_album.keys():
        if  key=='genre' or key=='composer' or key=='performer' or key=='label':
            value=album_info.get(key)
            if value is not None:
                value=value.get('name')
            else:
                continue
        else:
            value=album_info.get(key)

        if not value:
            continue
        if key=='artists':
            for artist in value:
                name = artist.get('name')
                if name is not None:
                    info_public += f'Artist: {name}\n'
                else:
                    continue
            continue
        info_public += '{}: {}\n'.format(dict_album[key], value)



    image_large= album_info.get('image').get('large','')
    if image_large:
        info_public += f'Cover: {image_large}\n'

    image_small = album_info.get('image').get('small','')
    if image_small:
        info_public += f'CoverPreview: {image_small}\n'

    dict_track = {"performer": 'Artist', 'title': 'Title', 'track_number': 'Track',
                  'release_date_original': 'Date','duration': 'Time','maximum_sampling_rate': 'Format',}

    info,track_all,play_index = append_song_info(dict_track,info_public,track_id,tracks)
    return save_song_info_and_play(info, album_id, track_all,type=type)

def qobuz_play_playlist(parameter,type):#parameter 一般包含playlist_id和track_id 至少包含playlist_id
    params_dic = api.td_qobuz_parameter_dic(parameter)
    if isinstance(params_dic, str):
        return '200'
    playlist_id = params_dic.get('playlist_id')
    track_id = params_dic.get('track_id')
    # params_dic['id'] = playlist_id
    try:
        track_info=api.td_qobuz_playlist_get(parameter=f'playlist_id={playlist_id}&extra=tracks&limit=500')
        if track_info.get('vit_status')==0:
            tracks=track_info.get('tracks').get('items')
        else:return track_info
    except:
        return '{"vit_status":4,"vit_message":"888"}'
    dict_track = {'title': 'Title', "performer": 'Artist', 'album': 'Album','track_number':'Track','release_date_original': 'Date',
                  'cover': 'CoverPreview', 'maximum_sampling_rate': 'Format','duration': 'Time'}
    info_public = ''

    info, track_all, play_index = append_song_info(dict_track, info_public, track_id, tracks)
    return save_song_info_and_play(info, playlist_id, track_all,type=type)


def qobuz_play_seach_tracks(parameter,type):
    parameter_dic = api.td_qobuz_parameter_dic(parameter)
    if isinstance(parameter_dic, str):
        return '200'

    track_id = parameter_dic.get('track_id')
    index = parameter_dic.get('track_index')  # 客户端传入的偏移量
    total = parameter_dic.get('total')
    query = parameter_dic.get('query')
    if not track_id or not query:
        return '{"vit_status":4,"vit_message":"444"}'


    if not index or not index.isdigit():
        index = 0

    parameter_dic['offset'] = index
    parameter_dic['limit'] = 100
    return_tracks = int(total) - int(index) - 1  # 计算剩余的歌曲数目

    if return_tracks > 100:

        try:
            track_info = api.td_qobuz_track_search(
                parameter=f"query={query}&limit={parameter_dic['limit']}&offset={parameter_dic['offset']}")


        except Exception:
            return '{"vit_status":4,"vit_message":"888"}'

    else:
        offset = int(parameter_dic['offset']) - (100 - return_tracks)
        if offset < 0:
            offset = 0
        parameter_dic['offset'] = offset
        track_info = api.td_qobuz_track_search(
            parameter=f"query={query}&limit={parameter_dic['limit']}&offset={parameter_dic['offset']}")
    tracks = track_info.get('tracks').get('items')

    dict_track = {'title': 'Title', "performer": 'Artist', 'label': 'Label', 'track_number': 'Track',
                  'genre': 'Genre', 'album': 'Album', 'cover': 'CoverUncertainty', 'maximum_sampling_rate': 'Format',
                  'duration': 'Time', 'releaseDate': 'Date', 'composer': 'Composer'}

    info_public = ''
    info, track_all, play_index = append_song_info(dict_track, info_public, track_id, tracks)


    if -1 != play_index:
        return save_song_info_and_play(info, track_id, track_all,type=type)

    try:
        track_info = api.td_qobuz_track_get(parameter=f'track_id={track_id}')
        vit_status = track_info.get('vit_status')
        if vit_status == 0:
            playlist_add = track_info.get('id')
            if playlist_add:
                track_url = f'{vit_prefix}{playlist_add}\n'
                track_all.insert(0, track_url)
                info += 'song_begin: {}'.format(track_url)

                dict_track = {'title': 'Title', "performer": 'Artist', 'track_number': 'Track', 'album': 'Album',
                              'cover': 'Cover', 'maximum_sampling_rate': 'Format', 'duration': 'Time'}
                for key in dict_track.keys():
                    if key == 'performer':
                        value = track_info.get(key).get('name')
                    elif key == 'album':
                        value = track_info.get(key).get('title')
                    elif 'cover' == key:
                        value = track_info.get('album').get('image')
                        cover = value.get('large')
                        coverpreview = value.get('small')
                        info += f'Cover: {cover}\nCoverPreview: {coverpreview}\n'
                        continue
                    elif 'maximum_sampling_rate' == key:
                        sampling_rate = track_info.get('maximum_sampling_rate', '*')
                        bit_depth = track_info.get('maximum_bit_depth', '*')
                        channel_count = track_info.get('maximum_channel_count', '*')
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
                    else:
                        value = track_info.get(key)
                    if not value:
                        continue
                    if key == 'duration':
                        info += f'duration: {value}'
                    info += '{}: {}\n'.format(dict_track[key], value)
                info += 'song_end\n'
                return save_song_info_and_play(info, track_id, track_all, type=type)
        else: return json.dumps(track_info)
    except:
        return '{"vit_status":4,"vit_message":"886"}'


def qobuz_play_my_track(parameter,type='w+'):#parameter：必需包含track_id/track_index.

    parameter_dic=api.td_qobuz_parameter_dic(parameter)
    if isinstance(parameter_dic,str):
        return  '200'
    try:
        track_id=parameter_dic.get('track_id')
        index = parameter_dic.get('track_index')#客户端传入的偏移量
        total=parameter_dic.get('total')
    except:
        return '{"vit_status":4,"vit_message":"444"}'
    if not index or not index.isdigit():
        index=0

    parameter_dic['offset']=index
    parameter_dic['limit'] = 100
    return_tracks=int(total)-int(index)-1#计算剩余的歌曲数目




    if return_tracks>100:

        try:
            track_info = api.td_qobuz_favorite_getUserFavorites(
                parameter=f"type=tracks&limit={parameter_dic['limit']}&offset={parameter_dic['offset']}")

        except Exception:
            return '{"vit_status":4,"vit_message":"888"}'

    else:
        offset=int(parameter_dic['offset'])-(100-return_tracks)
        if offset<0:
            offset=0
        parameter_dic['offset']=offset
        track_info = api.td_qobuz_favorite_getUserFavorites(
                parameter=f"type=tracks&limit={parameter_dic['limit']}&offset={parameter_dic['offset']}")
    tracks = track_info.get('tracks').get('items')

    total = track_info.get('tracks').get('total')
    # 如果收藏的歌曲大于等于100首而返回的歌曲不足一百首的话调整offset重新获取
    if int(total) >= 100 and len(tracks) < 100:
        parameter_dic['offset'] = int(parameter_dic['offset']) - (100 - len(tracks))
        track_info = api.td_qobuz_favorite_getUserFavorites(
            parameter=f"type=tracks&limit={parameter_dic['limit']}&offset={parameter_dic['offset']}")
        tracks = track_info.get('tracks').get('items')


    dict_track = {'title': 'Title', "performer": 'Artist', 'label': 'Label', 'track_number': 'Track',
                  'genre': 'Genre','album': 'Album', 'cover': 'CoverUncertainty', 'maximum_sampling_rate': 'Format',
                  'duration': 'Time','releaseDate': 'Date', 'composer': 'Composer'}

    info_public =''
    info, track_all, play_index = append_song_info(dict_track, info_public, track_id, tracks)
    if -1 != play_index:
        return save_song_info_and_play(info, track_id, track_all,type=type)

    try:
        track_info = api.td_qobuz_track_get(parameter=f'track_id={track_id}')
        vit_status = track_info.get('vit_status')
        if vit_status==0:
            playlist_add=track_info.get('id')
            if playlist_add:
                track_url = f'{vit_prefix}{playlist_add}\n'
                track_all.insert(0, track_url)
                info += 'song_begin: {}'.format(track_url)

                dict_track = {'title': 'Title', "performer": 'Artist', 'track_number': 'Track', 'album': 'Album',
                              'cover': 'Cover', 'maximum_sampling_rate': 'Format', 'duration': 'Time'}
                for key in dict_track.keys():
                    if key=='performer':
                        value =track_info.get(key).get('name')
                    elif key=='album':
                        value=track_info.get(key).get('title')
                    elif 'cover' == key:
                        value = track_info.get('album').get('image')
                        cover = value.get('large')
                        coverpreview = value.get('small')
                        info += f'Cover: {cover}\nCoverPreview: {coverpreview}\n'
                        continue
                    elif 'maximum_sampling_rate'==key:
                        sampling_rate = track_info.get('maximum_sampling_rate', '*')
                        bit_depth = track_info.get('maximum_bit_depth', '*')
                        channel_count = track_info.get('maximum_channel_count', '*')
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
                    else:
                        value = track_info.get(key)
                    if not value:
                        continue
                    if key=='duration':
                        info+=f'duration: {value}'
                    info += '{}: {}\n'.format(dict_track[key], value)
                info += 'song_end\n'
                return save_song_info_and_play(info, track_id, track_all,type=type)
    except:
        return '{"vit_status":4,"vit_message":"886"}'


# 将歌曲信息存储起来，然后调用mpd的播放功能
def save_song_info_and_play(info, playlist_id, track_all,type):
    info_dir = os.path.dirname(app_song_info)
    if not os.path.exists(info_dir):
        os.makedirs(info_dir)
    with open(app_song_info, type, encoding='utf8')as f:
        f.write(info)

    with open(qobuz_m3u8_path, mode='w+', encoding='utf8')as f3:
        f3.write(''.join(track_all))
    if type=='w+':
        #修改开始播放默认第一首歌 也就是客户端选中的那首歌 这样才不会在随机播放的模式下无法播放客户端选中的歌曲
        os.system('mpc clear > /dev/null 2>&1 && mpc load {}  > /dev/null 2>&1 && mpc play 1 > /dev/null 2>&1'.format(
            qobuz_m3u8_path))
    elif type=='a+':
        os.system('mpc load {}  > /dev/null 2>&1'.format(qobuz_m3u8_path))
    return '{"vit_status":0,"vit_message":"' + playlist_id + '"}'

def append_song_info(dict_track,info_public,track_id,tracks):
    play_index=-1
    info=''
    track_all= []
    for index,track in enumerate(tracks):
        playlist_add=track.get('id')
        if not playlist_add:
            continue
        if str(track_id)==str(playlist_add):
            play_index=index
        track_url=f"{vit_prefix}{playlist_add}\n"

        if -1==play_index:
            track_all.append(track_url)
        else:
            track_all.insert(index-play_index,track_url)

        info +='song_begin: {}'.format(track_url)

        for key in dict_track.keys():
            if key=='artist' or key=='performer' or key=='composer':
                   value=track.get(key)
                   if not value:
                       continue
                   else:
                       value=value.get('name')
            elif 'cover'==key:
                value=track.get('album').get('image')
                cover = value.get('large')
                coverpreview = value.get('small')
                info += f'Cover: {cover}\nCoverPreview: {coverpreview}\n'
                continue
            elif key =='album':
                value = track.get(key).get('title')
            elif 'release_date_original'==key:
                value=track.get('release_date_original')
                if not value:
                    value=track.get('album')
                    if not value:
                        continue
                    else:
                        value=value.get('release_date_original')


            else:
                value=track.get(key)
            if not value:
                continue
            mpd_key=dict_track[key]
            if 'maximum_sampling_rate'==key:
                sampling_rate=track.get('maximum_sampling_rate','*')
                bit_depth=track.get('maximum_bit_depth','*')
                channel_count=track.get('maximum_channel_count','*')

                try:
                    if float(sampling_rate)>384:
                        byt=int(float(sampling_rate)*100)
                    else:
                        byt = int(float(sampling_rate) * 1000)
                    value=f"{byt}:{bit_depth}:{channel_count}"
                    if value=='*:*:*':
                        continue
                except:
                    pass
            if key =='duration':
                info+=f'duration: {value}\n'

            info +=f'{mpd_key}: {value}\n'
        info+=info_public+'song_end\n'
    return info,track_all,play_index



def main():
    vit_status=initialize_api()
    if vit_status.get('vit_status')!=0:
        print(vit_status)
        sys.exit(98)

    try:
        qobuz_manage = sys.argv[1]
    except IndexError:
        print('{"vit_status":98,"vit_message":"986"}')
        sys.exit(98)
    try:
        qobuz_parameter = sys.argv[2]
    except IndexError:
        qobuz_parameter = ''

    if qobuz_manage == 'track_url':  # 获取歌曲链接
        url = qobuz_get_url_by_id(parameter=qobuz_parameter)
        if url.startswith('http://') or url.startswith('https://'):
            print(url)

    elif qobuz_manage == "add_track":  # 下一首播放；加到播放队列
        print(qobuz_next_track(parameter=qobuz_parameter))
    elif qobuz_manage == 'play_album':#播放专辑
        print(qobuz_play_album(parameter=qobuz_parameter,type='w+'))
    elif qobuz_manage == 'play_playlist':#播放歌单
        print(qobuz_play_playlist(parameter=qobuz_parameter,type='w+'))
    elif qobuz_manage == 'play_my_track':#播放我的歌曲
        print(qobuz_play_my_track(parameter=qobuz_parameter,type='w+'))
    elif qobuz_manage=='playlist_add_album':
        print(qobuz_play_album(parameter=qobuz_parameter, type='a+'))

    elif qobuz_manage=='playlist_add_playlist':
        print(qobuz_play_playlist(parameter=qobuz_parameter,type='a+'))

    elif qobuz_manage=='play_seach_track':
        print(qobuz_play_seach_tracks(parameter=qobuz_parameter,type='w+'))

    elif qobuz_manage=='play_seach_one':
        print(qobuz_next_track(parameter=qobuz_parameter,flag='w+'))
    else:
        print('{"vit_status":98,"vit_message":"987"}')
        sys.exit(98)

if __name__ == '__main__':
    main()
    # initialize_api()
    # print(qobuz_play_seach_one(parameter='track_id=1067057', type='a+'))

    # qobuz_parameter='track_id=122716434&track_index=114'
    # print(qobuz_play_album(parameter='album_id=uadfl29w9gsmb',type='w+'))
    # print(qobuz_play_album(parameter='album_id=vewzc8hmoqc8a',type='a+'))
    # print(qobuz_get_url_by_id(parameter='track_id=126785725'))
    # print(qobuz_add_track(parameter='track_id=126785725'))
    # print(qobuz_play_playlist(parameter='playlist_id=2136915',type='w+'))
    # print(qobuz_play_my_track(parameter='track_id=126785725&track_index=5'))






