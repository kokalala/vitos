import os
import time
from fastapi import BackgroundTasks
from mainfun import *
import base64


def cacheNextPage(jsonData):
    nextUrl = jsonData.get("content", {}).get("pagination", {}).get('next')
    if nextUrl:
        asyncCache(nextUrl)


def loadL2Cache(path, isL2Cache):
    """
    二级缓存
    :param path: 缓存的文件路径
    :param isL2Cache: 是否二级缓存，-1:不执行，0：执行下一页，1~20：缓存1-20个，99缓存全部
    :return: 不返回数据，将需要缓存的url添加到cacheList列表，让线程执行
    """
    if os.path.exists(path):
        with open(path, mode='r+', encoding='utf8') as f:
            readData = f.read()
            f.close()
        try:
            jsonData = json.loads(readData)
        except Exception as e:
            logger.exception("What?!")
            return
        entries = jsonData.get('content', {}).get('entries', [])
        if isL2Cache > 0:
            count = 0
            for data in entries:
                if count == isL2Cache:
                    break
                count += 1
                url = data.get('url')
                if url:
                    if 'album' in url or 'playlist' in url:  # 只对播放列表和专辑进行缓存
                        if len(cacheAmazonList) < cacheListLimit and url not in cacheAmazonList:
                            cacheAmazonList.append(url)
                            print("add url:{} to cacheAmazonList, time:{}".format(url, time.time()), len(cacheAmazonList))


def getPlayUrl(url: str):
    """
    获取播放地址
    url：曲目的url
    background_tasks：
    quality:音质，['Normal', 'High', 'HiFi', 'Master']
    """
    url = unquote(url)
    data = requestAirableplayer(url, isRefresh=0, cacheTime=10 * 365 * 24 * 60 * 60)
    print(data)
    if data.get('vit_status') == 0:
        stream = data.get('streams')
        if stream:
            stream_url = stream[0].get('url')
            track_info = requestAirableplayer(stream_url, cacheTime=60 * 20)  # 有效时间20分钟
            play_url = track_info.get('url')
            print(play_url)
            if play_url:
                return play_url
    return 'stream is None'  # 没有播放链接


def amazon_add_track(parameter, background_tasks, flag='a+'):
    """
    单个曲目添加
    --原函数，没有改动
    """
    if not parameter:
        return '200'
    key_list = ['Artist', 'Album', 'AlbumArtist', 'Title', 'Track', 'Genre', 'Date',
                'Cover', 'CoverPreview', 'Label', 'Composer', 'Time', 'duration', 'Format']
    track_id = ''
    params = ''
    track_uri = parameter.get('track_url')
    # background_tasks.add_task(requestAirable, track_uri)
    model = parameter.get('model', 'insert')
    for key in key_list:
        if key in parameter.keys():
            params += '{}: {}\n'.format(key, parameter.get(key))
    if not track_uri or track_uri == '没有该字段':
        return {"vit_status": 4, "vit_message": "403"}
    track_url = vit_prefix_amazon + track_uri
    info = 'song_begin: {}\n{}song_end\n'.format(track_url, params)
    info_dir = os.path.dirname(app_song_info)
    if not os.path.exists(info_dir):
        os.makedirs(info_dir)
    with open(app_song_info, flag, encoding='utf8') as f:
        f.write(info)
    print('model', model, flag)
    if flag == 'w+':
        os.popen(f'{COMMAND_MPC} clear > /dev/null 2>&1 && {COMMAND_MPC} add {track_url}  > /dev/null 2>&1 && {COMMAND_MPC} play > /dev/null 2>&1')
    else:
        if model == 'insert':
            os.popen(f'{COMMAND_MPC} insert {track_url}  > /dev/null 2>&1')
        # elif model == 'play':
        #     data = "".join(os.popen('mpc').readlines()).strip()
        #     count = int(re.findall(r"/(.+?)  ", data)[0])+1
        #     os.popen('mpc add {}  > /dev/null 2>&1  && mpc play {} > /dev/null 2>&1'.format(track_url,count))
        # os.popen('mpc insert {}  > /dev/null 2>&1 && mpc next > /dev/null 2>&1 && mpc play > /dev/null 2>&1'.format(track_url))
        elif model == 'add':
            os.popen(f'{COMMAND_MPC} add {track_url}  > /dev/null 2>&1')

    return {"vit_status": 0, "vit_message": track_id}


def maybe_login():
    """
    查询是否登录
    """
    url = "https://meta.airable.io/amazon"
    data = getUrl(url)
    if data.get('description') != "Use control app to log in.":
        setAmazonLoginStatus(True)
        return {'vit_status': 0, 'vit_message': '', "login": True}
    else:
        try:
            login_url = data.get('buttons')[2].get('url')
        except:
            login_url = ''
    setAmazonLoginStatus(False)
    return {'vit_status': 1, 'vit_message': '101', "login": False, 'login_url': login_url}


def amazon_logout():
    """
    amazon退出登录
    """
    logout_url = 'https://meta.airable.io/amazon/logout'
    info = ''
    skip_amazon = False
    try:
        os.system(f'{COMMAND_MPC} playlistdel http://online.silentangel.audio/amazon > /dev/null 2>&1')
        with open(app_song_info, encoding='utf8') as f:
            for line in f:
                if line.startswith('song_begin: ' + vit_prefix_amazon):
                    skip_amazon = True
                if skip_amazon:
                    if line.startswith('song_end'):
                        skip_amazon = False
                    continue
                else:
                    info += line
        with open(app_song_info, 'w+', encoding='utf8') as f:
            f.write(info)
    except:
        pass
    data = requestAirable(logout_url, isRefresh=1)
    clearCache('amazon')  # 执行删除缓存
    delCacheFile(sessionJson, mainFlag=True)  # 删除airabletoken
    setAmazonLoginStatus(False)  # 设置amazon是否登录状态
    return data


def quality_set(quality):
    """
    设置播放音质
    quality：['Master', 'HiFi', 'High', 'Normal']
    """
    quality_list = ['Master', 'HiFi', 'High', 'Normal']
    if quality not in quality_list:
        quality = "Master"
    try:
        with open(quality_info, 'w+', encoding='utf8') as f:
            f.write(quality)
        return {'vit_status': 0, 'vit_message': ''}
    except:
        return {'vit_status': 4, 'vit_message': '444'}


def asyncCache(url, flag=False):
    """
    background_tasks.add_task(asyncCache, url)
    后台运行下载缓存
    asyncCacheList：缓存列表，如果有缓存在运行，就退出
    """
    # print('asyncCacheList1:', asyncCacheList,url in asyncCacheList)
    if url not in asyncCacheAmazonList or flag:

        asyncCacheAmazonList.append(url)
        try:
            # requestAirable(url, isRefresh=1)
            data = amazon_check_data(getUrl(url))
            if data['vit_status'] == 0:  # 如果获取到数据
                path = urlToPath(url, cacheAmazonDir)
                writeCacheFile(path, data)
        except:
            pass
        asyncCacheAmazonList.remove(url)


def asyncExec(url: str):
    """
    异步执行url，不缓存
    :param url: 执行的url,如果url带有‘r=/’,刷新r=/后的缓存
    :return:
    """
    getUrl(url)
    if 'r=/' in unquote(url):
        asyncCache(airableHost + unquote(url).split('r=/')[1], flag=True)


def requestAirable(url, isRefresh=0, cacheTime=cacheDefaultTime, isL2Cache=-1, background_tasks=None):
    """
    sRefresh:是否强制刷新
    cacheTime：缓存时间
    isL2Cache是否二级缓存，-1：不缓存，0：缓存下一页，1~98：缓存数量，99：全部缓存
    """
    path = urlToPath(url, cacheAmazonDir)
    if os.path.exists(path) and isRefresh == 0:
        mtime = os.stat(path).st_mtime  # 获取文件的修改时间
        try:
            with open(path, mode='r+', encoding='utf8') as f:
                readData = json.loads(f.read())
                f.close()
            if abs(int(time.time() - mtime)) < cacheTime:
                if isL2Cache > -1 and 'amazon/search' not in url and background_tasks is not None:
                    background_tasks.add_task(loadL2Cache, path, isL2Cache)  # 二级缓存队列
                if 'amazon/search' not in url and background_tasks is not None:  # 搜索页面不刷新缓存
                    background_tasks.add_task(asyncCache, url)
                if background_tasks is not None:  # 加载下一页
                    background_tasks.add_task(cacheNextPage, readData)
                return readData
        except:  # 获取缓存错误后，请求网络
            logger.exception("What?!")
            pass
    if isRefresh == 1 and ("p=1" in url or "p=" not in url):  # 如果是强制刷新，清除第二页以下的缓存
        for k, v in allAmazonOrder.items():
            if v in url:
                delCacheFile(path.split("?")[0] + "*")
                break
    data = amazon_check_data(getUrl(url))
    if data['vit_status'] in [0]:  # 如果获取到数据
        writeCacheFile(path, data)
    else:
        delCacheFile(path, mainFlag=True)  # 遇到错误删除缓存
    if isL2Cache > -1 and 'amazon/search' not in url and background_tasks is not None:
        background_tasks.add_task(loadL2Cache, path, isL2Cache)  # 二级缓存队列
    if background_tasks is not None:  # 加载下一页
        background_tasks.add_task(cacheNextPage, data)
    return data


def requestAirableplayer(url, isRefresh=0, cacheTime=cacheDefaultTime, isL2Cache=-1, background_tasks=None):
    """
    获取播放链接
    sRefresh:是否强制刷新
    cacheTime：缓存时间
    isL2Cache是否缓存
    """
    path = urlToPath(url, cacheAmazonDir)
    if os.path.exists(path) and isRefresh == 0:
        mtime = os.stat(path).st_mtime  # 获取文件的修改时间
        try:
            with open(path, mode='r+', encoding='utf8') as f:
                readData = json.loads(f.read())
                f.close()
            if abs(int(time.time() - mtime)) < cacheTime:
                return readData
        except:
            logger.exception("What?!")
            pass
    data = amazon_check_data(getUrl(url))
    if data['vit_status'] in [0]:  # 如果获取到数据
        writeCacheFile(path, data)
    else:
        delCacheFile(path, mainFlag=True)
    return data


def mkCacheDir(dirName):
    """
    创建缓存文件夹
    """
    path = os.path.exists(os.path.join(cacheAmazonDir, dirName))
    if not path:  # 创建缓存文件夹
        os.makedirs(path)
    return path


def delCacheFile(filePath, mainFlag=False):  # 清除文件
    """
        filePath：删除路径
        mainFlag：是否包含cacheTidalDir
    """
    try:
        if not mainFlag:
            file = os.path.join(cacheAmazonDir, filePath)
        else:
            file = filePath
        print("rm -f {}".format(file))
        file = file.replace("&", "\&")
        os.popen("rm -f {}".format(file))
    except:
        pass


def initAmazon():
    """
    初始化加载页面
    用户登录后，调用该接口
    """
    modules = ['new_playlist', 'new_album', 'new_track']
    # modules = allAmazonOrder.keys()
    for module in modules:
        print(module)
        url = allAmazonOrder.get(module)
        asyncCache(url)
        # if url != '' and url not in cacheAmazonList:
        #     cacheAmazonList.append(url)
    print('initAmazon into cacheList:', len(cacheAmazonList))


def getDirSize(dir):
    """
    获取文件夹大小
    """
    size = 0
    for root, dirs, files in os.walk(dir):
        size += sum([os.path.getsize(os.path.join(root, name)) for name in files])
    return size


def actionsFavorites(url, background_tasks=None):
    """
    收藏专辑、歌曲、播放列表, 创建与删除我的播放列表 等操作时调用
    以上动作切换到后台执行，直接返回app成功
    """
    # os.popen('python {} asyncExec "url={}"'.format(projectFile,quote(url)))  # 异步向airable提交
    print('actionsFavorites')
    background_tasks.add_task(asyncExec, url)
    if "actions/amazon/album" in url:
        albumID = re.findall(r"/album/(.+?)/", url)
        delCacheFile("id/amazon/album/{}".format(albumID))  # 删除缓存
        delCacheFile("amazon/my/album*")  # 删除缓存
    elif "actions/amazon/playlist" in url:
        playlistID = re.findall(r"/playlist/(.+?)/", url)
        delCacheFile("id/amazon/playlist/{}".format(playlistID))  # 删除缓存
        delCacheFile("amazon/my/playlist*")  # 删除缓存
    elif "actions/amazon/track" in url:
        trackID = re.findall(r"/track/(.+?)/", url)
        delCacheFile("id/amazon/track/{}".format(trackID))  # 删除缓存
        delCacheFile("amazon/my/track*")  # 删除缓存
    elif "actions/amazon/artist" in url:
        playlistID = re.findall(r"/artist/(.+?)/", url)
        delCacheFile("id/amazon/artist/{}".format(playlistID))  # 删除缓存
        delCacheFile("amazon/my/artist*")  # 删除缓存
    if "r=/" in unquote(url):  # id/amazon/ablbum/221962069
        tmpPath = unquote(url).split('r=/')[1]
        delCacheFile(tmpPath)  # 删除缓存


def saveTrackInfo(cacheInfo):
    """
    保存曲目信息
    """
    entries = cacheInfo.get("content", {}).get("entries", [])
    for entrie in entries:
        if entrie.get('url'):
            path = urlToPath(entrie.get('url'), cacheAmazonDir)
            entrie["vit_status"] = 0
            entrie["vit_message"] = ""
            writeCacheFile(path, entrie)


def seachAmazon(parameterDic, isRefresh, cacheTime, isL2Cache, background_tasks):
    """
    搜索
    parameterDic：请求的参数
    isRefresh：强制刷新
    cacheTime：缓存时间
    isL2Cache：是否二级缓存
    background_tasks：后台执行对象
    """
    amazon_manage = parameterDic.get('amazon_manage')
    keywords = parameterDic.get('query', '')
    allItem = {
        "seach_albums": "https://meta.airable.io/amazon/document/" + base64.urlsafe_b64encode(
            f'["https:\/\/music-api.amazon.com\/search?keywords={keywords}&type=catalog_album&count=50#catalog_albums_search_desc"]'.encode()).decode('utf8'),
        "seach_playlists": "https://meta.airable.io/amazon/document/" + base64.urlsafe_b64encode(
            f'["https:\/\/music-api.amazon.com\/search?keywords={keywords}&type=catalog_playlist&count=50#catalog_playlists_search_desc"]'.encode()).decode('utf8'),
        "seach_tracks": "https://meta.airable.io/amazon/document/" + base64.urlsafe_b64encode(
            f'["https:\/\/music-api.amazon.com\/search?keywords={keywords}&type=catalog_track&count=50#catalog_tracks_search_desc"]'.encode()).decode('utf8'),
        "seach_artists": "https://meta.airable.io/amazon/document/" + base64.urlsafe_b64encode(
            f'["https:\/\/music-api.amazon.com\/search?keywords={keywords}&type=catalog_artist&count=50#catalog_artists_search_desc"]'.encode()).decode('utf8'),
        "seach_stations": "https://meta.airable.io/amazon/document/" + base64.urlsafe_b64encode(
            f'["https:\/\/music-api.amazon.com\/search?keywords={keywords}&type=catalog_artist&count=50#catalog_stations_search_desc"]'.encode()).decode('utf8'),

        # "seach_artists": f"https://music-api.amazon.com/search?keywords={keywords}&type=catalog_artist&count=50#catalog_artists_search_desc"
    }
    # print(allItem.get(amazon_manage))
    for key in allItem.keys():
        if key == amazon_manage:  # 当前搜索的数据
            url: str = allItem.get(amazon_manage).format(**parameterDic)  # 传参到url
            data = requestAirable(url, isRefresh=isRefresh, cacheTime=cacheTime, isL2Cache=isL2Cache)
            nextUrl = data.get("content", {}).get("pagination", {}).get('next')
            if nextUrl:
                background_tasks.add_task(asyncCache, nextUrl)
        else:
            background_tasks.add_task(asyncCache, allItem.get(key).format(**parameterDic))  # 其他不同的搜索后台执行
    return data


def playListOrAlbum(playlist_url: str, playType, track_url, background_tasks, pageLimit=False):
    global amazonPlayFlag
    """
    播放
    playlist_url:播放列表 或 专辑 的链接
    playType：w+ 播放整个列表或专辑；a+ 添加到播放队列
    track_url: 从此曲目开始播放整个播放列表或专辑
    background_tasks:后台执行对象
    pageLimit: 针对艺术家->曲目，100首歌（第6页）曲以后的歌曲，并不是艺术家本人的歌曲
    """
    if playType == 'w+':
        amazonPlayFlag = time.time()
    playlistInfo = requestAirable(playlist_url)
    if int(playlistInfo.get('vit_status')) != 0:
        return playlistInfo
    pages = playlistInfo.get('content', {}).get('pagination', {}).get('pages', {}).get('values', [1])  # 总页数
    # 遍历当前页歌曲 如果未找到播放链接则直接返回提示
    beforeData = []  # [{'tracks':list,'info':list}]  #保存前段部分
    afterData = []  # [{'tracks':list,'info':list}]  # 保存后段部分
    tempUrls = []  # 保存剩余部分
    flag = False  # 是否等于从此曲播放
    # 1.整专辑播放，加载第一页到播放列表，其他页后台加载
    # 2.从此曲目播放，for循环找到该曲目后，其余部分后台加载
    if pageLimit:
        if len(pages) > 5:
            pages = pages[:5]
    for page in pages:
        if not flag:
            if page != 1:
                playlistInfo = requestAirable(f'{playlist_url}?p={page}')

            saveTrackInfo(playlistInfo)
            entries = playlistInfo.get('content', {}).get('entries', [])
            for entrie in entries:
                if playlistInfo.get('type') == 'album':  # album 的年份在外面
                    if entrie.get('album'):
                        entrie['album']['release'] = playlistInfo.get('release')
                url = entrie.get('url')
                if url != track_url and not flag and url:
                    beforeData.append({'track': f'{vit_prefix_amazon}{url}', 'info': getTrackInfo(entrie)})
                elif (url == track_url or flag) and url:
                    flag = True
                    afterData.append({'track': f'{vit_prefix_amazon}{url}', 'info': getTrackInfo(entrie)})
            if track_url is None:
                flag = True
        else:
            tempUrls.append(f'{playlist_url}?p={page}')
    if track_url:  # 从此曲目播放
        if afterData:
            save_song_info_and_play(afterData, playType)
            background_tasks.add_task(playListOrAlbumThreading, tempUrls, beforeData, amazonPlayFlag)
        else:
            return {'vit_status': 4, 'vit_message': "403"}
    else:  # 整专辑播放，执行播放或加载第一页
        if beforeData:
            save_song_info_and_play(beforeData, playType)
            background_tasks.add_task(playListOrAlbumThreading, tempUrls, [], amazonPlayFlag)
        else:
            return {'vit_status': 4, 'vit_message': "403"}
    return {'vit_status': 0, 'vit_message': playlist_url}


def playListOrAlbumThreading(urls, trackDatas, PlayFlag):
    """
    线程添加播放列表到播放器
    """
    global amazonPlayFlag
    threadPool = ThreadPoolExecutor(max_workers=6)
    count = 0
    track_dic = []
    tracks_list = []  # [{'tracks':list,'info':list}]
    for url in urls:
        track_dic.append([])
        threadPool.submit(threadingTracks, url, track_dic[count])
        count += 1
        if count >= 5 and ('playlist' not in url or 'album' not in url):  # 如果不是playlist或album只加载5页
            break
    threadPool.shutdown(wait=True)
    for i in range(count):
        tracks_list += track_dic[i]
    trackDatas = tracks_list + trackDatas
    time.sleep(1)  # 延时一秒写入，如果写过覆盖之前的，之前运行mpc会加载到这个文件
    if amazonPlayFlag == PlayFlag:
        save_song_info_and_play(trackDatas, 'a+')
    print('playListOrAlbumThreading finish:', str(count))


def threadingTracks(playlist_url, trackDic):
    """
    获取播放列表或专辑下面的曲目信息
    """
    playlistInfo = requestAirable(playlist_url)
    saveTrackInfo(playlistInfo)
    entries = playlistInfo.get('content', {}).get('entries', [])
    for entrie in entries:
        if playlistInfo.get('type') == 'album':  # album 的年份在外面
            if entrie.get('album'):
                entrie['album']['release'] = playlistInfo.get('release')
        url = entrie.get('url')
        if url:
            trackDic.append({'track': f'{vit_prefix_amazon}{url}', 'info': getTrackInfo(entrie)})


def save_song_info_and_play(trackDatas, playType):
    """
    保持歌曲信息、mpc加载播放列表
    info:播放歌曲的信息
    track_all：需要加载的曲目
    playType：w+ 播放整个列表或专辑；a+ 添加到播放队列
    """
    track_all = [a['track'] for a in trackDatas]
    info = [a['info'] for a in trackDatas]
    info_dir = os.path.dirname(app_song_info)
    if not os.path.exists(info_dir):
        os.makedirs(info_dir)
    with open(app_song_info, playType, encoding='utf8') as f:
        f.write(''.join(info))
    with open(amazon_m3u8_path, mode='w+', encoding='utf8') as f3:
        f3.write('\n'.join(track_all))
    if playType == 'w+':
        # 修改开始播放默认第一首歌 也就是客户端选中的那首歌 这样才不会在随机播放的模式下无法播放客户端选中的歌曲
        # os.system(f'{COMMAND_MPC} clear > /dev/null 2>&1 && {COMMAND_MPC} load {amazon_m3u8_path}  > /dev/null 2>&1 && {COMMAND_MPC} play 1 > /dev/null 2>&1')
        os.popen(f'{COMMAND_MPC} clear > /dev/null 2>&1 && {COMMAND_MPC} load {amazon_m3u8_path}  > /dev/null 2>&1 && {COMMAND_MPC} play 1 > /dev/null 2>&1')
    elif playType == 'a+':
        os.popen(f'{COMMAND_MPC} load {amazon_m3u8_path}  > /dev/null 2>&1')


def getTrackInfo(infoJson: dict, prefix=vit_prefix_amazon):
    """
    返回曲目信息
    infoJson：曲目的json数据
    注意：字符串':'后面有空格
    """
    tarckId = infoJson.get('id', ['', '', None])
    if tarckId[0] != 'amazon' or tarckId[1] != 'track' or tarckId[2] is None:
        return ''
    strTemp = f"song_begin: {prefix}{infoJson.get('url', '')}\n" + \
              f"Title: {infoJson.get('title', '')}\n" + \
              f"Artist: {infoJson.get('artist', {}).get('title', '')}\n" + \
              f"Album: {infoJson.get('album', {}).get('title', '')}\n" + \
              f"Date: -\n" + \
              f"Cover: {infoJson.get('images', [''])[-1].get('url', '')}\n" + \
              f"CoverPreview: {infoJson.get('images', [''])[0].get('url', '')}\n" + \
              f"duration: {infoJson.get('duration', '0')}\n" + \
              f"Time: {infoJson.get('duration', '0')}\n" + \
              f"song_end\n"
    return strTemp


def amazon_play_station(parameter_dic):
    """
    播放amazon电台
    """
    station_url = parameter_dic.get('station_url')
    if not station_url:
        return {'vit_status': 2, 'vit_message': '201'}
    current_track_url = f"{station_prefix}{station_url}\n"
    os.system(
        f'{COMMAND_MPC} clear > /dev/null 2>&1 && {COMMAND_MPC} add {current_track_url} > /dev/null 2>&1 && {COMMAND_MPC} play > /dev/null 2>&1')
    os.system(f'{COMMAND_MPC} repeat off > /dev/null 2>&1')
    os.system(f'{COMMAND_MPC} single off > /dev/null 2>&1')
    os.system(f'{COMMAND_MPC} random off > /dev/null 2>&1')
    return {"vit_status": 0, "vit_message": current_track_url.replace("\"", '')}


def amazon_get_station_play_url(parameter_dic):
    """
    获取amazon播放url
    """
    if isinstance(parameter_dic, str):
        return '200'
    url = parameter_dic.get('track_id', '')
    data = getUrl(url)

    if data.get('vit_status') == 0:
        current_track_info = getTrackInfo(data, prefix=station_prefix)
        info_dir = os.path.dirname(app_song_info)
        if not os.path.exists(info_dir):
            os.makedirs(info_dir)

        with open(app_song_info, mode='w+', encoding='utf8') as f:
            f.write(current_track_info)

        current_track = data.get('content', {}).get('entries')[0]
        if not current_track:
            return json.dumps({'vit_status': 4, 'vit_message': '444'})
        stream_url = current_track.get('streams')[0].get('url', '')
        track_info = getUrl(stream_url)
        play_url = track_info.get('url')

        prev_url = data.get('content', {}).get('pagination', {}).get('prev', '')
        next_url = data.get('content', {}).get('pagination', {}).get('next', '')

        if play_url:
            return play_url, prev_url, next_url
        else:
            return '{"vit_status":4,"vit_message":"441"}'
    else:
        return data
