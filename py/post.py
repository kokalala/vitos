# *encoding=utf-8
import json
import os
import random
import sys
from urllib.parse import unquote
play_m3u8_path = "/tmp/vitos_play_list.m3u8"
app_song_info= '/mnt/mpd/app_song_info'



def get_parameter_dic(parameter):
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


    parameter=sys.argv[1]
    # print(parameter)
    parameter_dic=get_parameter_dic(parameter)
    data=parameter_dic.get('query')
    music_info=json.loads(data)
    # with open('./music_info')as f:
    #     music_info = json.load(f)

    # info = json.loads(data)
    tracks_info = music_info.get('song_info')
    action=music_info.get('model')
    if not action:
        print('{"vit_status":4,"vit_message":"401"}')
        os._exit(4)
    track_all = []
    song_info = ''

    for track in tracks_info:
        track_url=track.get("uri")

        if track_url:
            track_all.append(track_url)
            song_info += f"song_begin: {track_url}\n"

        else:
            continue
        for key in track.keys():
            if track.get(key)and key!='uri':
                info = key + ": " + track[key] + '\n'
                song_info += info
        song_info += 'song_end\n'
    # print(song_info)
    with open(play_m3u8_path, mode='w+', encoding='utf8')as f3:
        f3.write('\n'.join(track_all))
    # song_info = "".join(info_list)

    if action=='to_now':#现在就要播放
        with open(app_song_info,'w+')as f:
            f.write(song_info)
        os.system('mpc clear > /dev/null 2>&1 && mpc load {}  > /dev/null 2>&1 && mpc play 1 > /dev/null 2>&1'.format(play_m3u8_path))
        print('{"vit_status":0,"vit_message":""}')
    else :
        with open(app_song_info,'a+')as f:
            f.write(song_info)
        if action == "to_add":  # 添加到播放队列
            for track_uri in track_all:
                os.system('mpc add {}  > /dev/null 2>&1'.format(track_uri))
        elif action=='to_next':#添加到下一首播放
            os.system('mpc insert {}  > /dev/null 2>&1'.format(track_all[0]))
        print('{"vit_status":0,"vit_message":""}')







if __name__ == '__main__':
    main()
    # fun('')