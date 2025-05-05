import os
import time
from fastapi import BackgroundTasks
from config import *
from mainfun import *


def cacheNextPage(jsonData):
    """
    异步执行下一页缓存
    """
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
        except:
            pass
        # nextUrl = jsonData.get("content", {}).get("pagination", {}).get('next')
        # if nextUrl:
        #     asyncCache(nextUrl)
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
                        if len(cacheTidalList) < cacheListLimit and url not in cacheTidalList:
                            cacheTidalList.append(url)
                            print("add url:{} to cacheTidalList, time:{}".format(url, time.time()))


def getPlayUrl(url: str, quality='Master'):
    """
    获取播放地址
    url：曲目的url
    background_tasks：
    quality:音质，['Normal', 'High', 'HiFi', 'Master']
    """
    url = unquote(url)
    data = requestAirablePlayer(url, isRefresh=0, cacheTime=10 * 365 * 24 * 60 * 60)
    if data.get('vit_status') == 0:
        stream = data.get('streams')
        quality_list = ['Normal', 'High', 'HiFi', 'Master']
        if stream:
            index = quality_list.index(quality)
            stream_url = stream[-1].get('url') if quality == 'Master' else stream[index].get('url') if index + 1 < len(stream) else stream[-1].get('url')
            track_info = requestAirablePlayer(stream_url, cacheTime=60 * 50)  # 有效时间1小时
            play_url = track_info.get('url')
            print(play_url)
            if play_url:
                return play_url
    return "stream is None"  # 没有播放链接


def tidal_add_track(parameter, background_tasks, flag='a+'):
    """
    单个曲目添加
    --原函数，没有修改
    """
    if not parameter:
        return '200'
    key_list = ['Artist', 'Album', 'AlbumArtist', 'Title', 'Track', 'Genre', 'Date',
                'Cover', 'CoverPreview', 'Label', 'Composer', 'Time', 'duration', 'Format']
    track_id = ''
    params = ''
    track_uri = parameter.get('track_url')
    background_tasks.add_task(requestAirable, track_uri)
    model = parameter.get('model', 'insert')
    for key in key_list:
        if key in parameter.keys():
            params += '{}: {}\n'.format(key, parameter.get(key))
    if not track_uri or track_uri == '没有该字段':
        return {"vit_status": 4, "vit_message": "403"}
    track_url = vit_prefix_tidal + track_uri
    info = 'song_begin: {}\n{}song_end\n'.format(track_url, params)
    info_dir = os.path.dirname(app_song_info)
    if not os.path.exists(info_dir):
        os.makedirs(info_dir)
    with open(app_song_info, flag, encoding='utf8') as f:
        f.write(info)
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


def tidal_login_and_quality():
    """
    查询tidal是否登录
    """
    url = 'https://meta.airable.io/tidal/new/playlists'
    data = requestAirable(url, isRefresh=1)
    try:
        if data.get('description') == 'Please use your companion app to login':
            login = False
            setTidalLoginStatus(False)
            login_url = data.get('buttons')[1].get('url')
        else:
            setTidalLoginStatus(True)
            login = True
            login_url = ''
    except:
        return {'vit_status': 4, 'vit_message': '446'}
    try:
        with open(quality_info) as f:
            quality = f.read()
        if not quality:
            quality = 'Master'
    except:
        quality = 'Master'
    print("islogin:", {"vit_status": 0, 'vit_message': "", 'login': login, 'quality': quality, 'login_url': login_url})

    return {"vit_status": 0, 'vit_message': "", 'login': login, 'quality': quality, 'login_url': login_url}


def tidal_logout():
    """
    tidal退出登录
    """
    logout_url = 'https://meta.airable.io/tidal/logout'
    info = ''
    skip_tidal = False
    try:
        os.system(f'{COMMAND_MPC} playlistdel http://online.silentangel.audio/tidal > /dev/null 2>&1')
        with open(app_song_info, encoding='utf8') as f:
            for line in f:
                if line.startswith('song_begin: ' + vit_prefix_tidal):
                    skip_tidal = True
                if skip_tidal:
                    if line.startswith('song_end'):
                        skip_tidal = False
                    continue
                else:
                    info += line
        with open(app_song_info, 'w+', encoding='utf8') as f:
            f.write(info)
    except:
        pass
    data = requestAirable(logout_url, isRefresh=1)
    clearCache('tidal')  # 执行删除缓存
    delCacheFile(sessionJson, mainFlag=True)  # 删除airable的token
    setTidalLoginStatus(False)  # 设置tidal是否登录状态
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
    if url not in asyncCacheTidalList or flag:

        asyncCacheTidalList.append(url)
        try:
            #requestAirable(url, isRefresh=1)
            data = tidal_check_data(getUrl(url))
            if data['vit_status'] == 0:  # 如果获取到数据
                path = urlToPath(url, cacheTidalDir)
                writeCacheFile(path, data)
        except:
            pass
        asyncCacheTidalList.remove(url)


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
    isL2Cache是否缓存
    """

    path = urlToPath(url, cacheTidalDir)
    if os.path.exists(path) and isRefresh == 0:
        mtime = os.stat(path).st_mtime  # 获取文件的修改时间
        try:
            with open(path, mode='r+', encoding='utf8') as f:
                readData = json.loads(f.read())
                f.close()
            if abs(int(time.time() - mtime)) < cacheTime:
                if isL2Cache > -1 and 'tidal/search' not in url and background_tasks is not None:
                    background_tasks.add_task(loadL2Cache, path, isL2Cache)  # 二级缓存队列
                if 'tidal/search' not in url and background_tasks is not None:  # 搜索页面不刷新缓存
                    background_tasks.add_task(asyncCache, url)
                if background_tasks is not None:  # 加载下一页
                    background_tasks.add_task(cacheNextPage, readData)
                return readData
        except:  # 获取缓存错误后，请求网络
            logger.exception("What?!")
            pass
    if isRefresh == 1 and ("p=1" in url or "p=" not in url):  # 如果是强制刷新，清除第二页以下的缓存
        items = ["/tidal/new/playlists", "/tidal/new/albums", "/tidal/new/tracks", "/tidal/rising/albums", "/tidal/rising/tracks", "/tidal/master/albums",
                 "/tidal/master/playlists", "/tidal/playlists/moods", "/tidal/playlists/new", "/tidal/playlists/recommended", "/tidal/my/playlists",
                 "/tidal/my/albums", "/tidal/my/tracks", "/tidal/my/artists", "/tidal/genre"]
        for item in items:
            if item in url:
                delCacheFile(path.split("?")[0]+"*")
                break
    data = tidal_check_data(getUrl(url))
    if data['vit_status'] in [0]:  # 如果获取到数据
        writeCacheFile(path, data)
        if isL2Cache > -1 and 'tidal/search' not in url and background_tasks is not None:
            background_tasks.add_task(loadL2Cache, path, isL2Cache)  # 二级缓存队列
        if background_tasks is not None:  # 加载下一页
            background_tasks.add_task(cacheNextPage, data)
    else:
        delCacheFile(path, mainFlag=True)  # 遇到错误删除缓存

    return data


def requestAirablePlayer(url, isRefresh=0, cacheTime=cacheDefaultTime, isL2Cache=-1, background_tasks=None):
    """
    获取音乐链接
    sRefresh:是否强制刷新
    cacheTime：缓存时间
    isL2Cache是否缓存
    """
    path = urlToPath(url, cacheTidalDir)
    if os.path.exists(path) and isRefresh == 0:
        mtime = os.stat(path).st_mtime  # 获取文件的修改时间
        try:
            with open(path, mode='r+', encoding='utf8') as f:
                readData = json.loads(f.read())
                f.close()
            if abs(int(time.time() - mtime)) < cacheTime:
                if isL2Cache > -1 and 'tidal/search' not in url and background_tasks is not None:
                    background_tasks.add_task(loadL2Cache, path, isL2Cache)  # 二级缓存队列
                if 'tidal/search' not in url and background_tasks is not None:  # 搜索页面不刷新缓存
                    background_tasks.add_task(asyncCache, url)
                if background_tasks is not None:  # 加载下一页
                    background_tasks.add_task(cacheNextPage, readData)
                return readData
        except:
            logger.exception("What?!")
            pass
    data = tidal_check_data(getUrl(url))
    if data['vit_status'] in [0]:  # 如果获取到数据
        writeCacheFile(path, data)
    else:
        delCacheFile(path, mainFlag=True)
    if isL2Cache > -1 and 'tidal/search' not in url and background_tasks is not None:
        background_tasks.add_task(loadL2Cache, path, isL2Cache)  # 二级缓存队列
    if background_tasks is not None:  # 加载下一页
        background_tasks.add_task(cacheNextPage, data)
    return data


def mkCacheDir(dirName):
    """
    创建缓存文件夹
    """
    path = os.path.exists(os.path.join(cacheTidalDir, dirName))
    if not path:  # 创建缓存文件夹
        os.makedirs(path)
    return path


def delCacheFile(filePath, mainFlag=False):  # 清除文件
    """
    filePath：删除路径
    mainFlag：是否要包含cacheTidalDir路径
    """
    try:
        if not mainFlag:
            file = os.path.join(cacheTidalDir, filePath)
        else:
            file = filePath
        print("rm -f {}".format(file))
        file = file.replace("&", "\&")
        os.popen("rm -f {}".format(file))
    except:
        pass


def initTidal():
    """
    初始化加载页面--开机
    """
    # modules = ['new_playlist', 'new_album', 'new_track', 'rising_album', 'rising_track', 'master_album',
    #            'master_playlist', 'by_mood', 'playlist_new', 'recommended_playlist', 'genres', 'my_playlists',
    #            'my_albums', 'my_tracks', 'my_artists']
    modules = ['new_playlist', 'new_album', 'new_track']
    for module in modules[::-1]:
        print(module)
        url = allTidalOrder.get(module)
        asyncCache(url)
        # if url != '' and url not in cacheTidalList:
        #     cacheTidalList.append(url)
    print('initTidal into cacheList:', len(cacheTidalList))


def getDirSize(dir):
    """
    获取文件夹大小
    """
    size = 0
    for root, dirs, files in os.walk(dir):
        size += sum([os.path.getsize(os.path.join(root, name)) for name in files])
    return size


def actionsFavorites(url, background_tasks=None):  # 收藏专辑、歌曲、播放列表, 创建与删除我的播放列表
    """
    收藏专辑、歌曲、播放列表, 创建与删除我的播放列表 等操作时调用
    以上动作切换到后台执行，直接返回app成功
    """
    # os.popen('python {} asyncExec "url={}"'.format(projectFile,quote(url)))  # 异步向airable提交
    print('actionsFavorites')
    background_tasks.add_task(asyncExec, url)
    if "actions/tidal/album" in url:
        albumID = re.findall(r"/album/(.+?)/", url)
        delCacheFile("id/tidal/album/{}".format(albumID))  # 删除缓存
        delCacheFile("tidal/my/album*")  # 删除缓存
    elif "actions/tidal/playlist" in url:
        playlistID = re.findall(r"/playlist/(.+?)/", url)
        delCacheFile("id/tidal/playlist/{}".format(playlistID))  # 删除缓存
        delCacheFile("tidal/my/playlist*")  # 删除缓存
    elif "actions/tidal/track" in url:
        trackID = re.findall(r"/track/(.+?)/", url)
        delCacheFile("id/tidal/track/{}".format(trackID))  # 删除缓存
        delCacheFile("tidal/my/track*")  # 删除缓存
    elif "actions/tidal/artist" in url:
        playlistID = re.findall(r"/artist/(.+?)/", url)
        delCacheFile("id/tidal/artist/{}".format(playlistID))  # 删除缓存
        delCacheFile("tidal/my/artist*")  # 删除缓存
    if "r=/" in unquote(url):  # id/tidal/ablbum/221962069
        tmpPath = unquote(url).split('r=/')[1]
        delCacheFile(tmpPath)  # 删除缓存


def saveTrackInfo(cacheInfo):
    """
    保存曲目信息
    """
    entries = cacheInfo.get("content", {}).get("entries", [])
    for entrie in entries:
        if entrie.get('url'):
            path = os.path.join(cacheTidalDir, "id/tidal/track/{}".format(entrie['id'][2]))
            entrie["vit_status"] = 0
            entrie["vit_message"] = ""
            writeCacheFile(path, entrie)


def seachTidal(parameterDic, isRefresh, cacheTime, isL2Cache, background_tasks):
    """
    搜索
    parameterDic：请求的参数
    isRefresh：强制刷新
    cacheTime：缓存时间
    isL2Cache：是否二级缓存
    background_tasks：后台执行对象
    """
    tidal_manage = parameterDic.get('tidal_manage')
    allItem = {
        "seach_albums": "https://meta.airable.io/tidal/search/albums?q={query}",
        "seach_playlists": "https://meta.airable.io/tidal/search/playlists?q={query}",
        "seach_tracks": "https://meta.airable.io/tidal/search/tracks?q={query}",
        "seach_artists": "https://meta.airable.io/tidal/search/artists?q={query}"
    }
    for key in allItem.keys():
        if key == tidal_manage:
            url: str = allItem.get(tidal_manage).format(**parameterDic)  # 传参到url
            data = requestAirable(url, isRefresh=isRefresh, cacheTime=cacheTime, isL2Cache=isL2Cache)
            nextUrl = data.get("content", {}).get("pagination", {}).get('next')
            if nextUrl:
                background_tasks.add_task(asyncCache, nextUrl)
        else:
            background_tasks.add_task(asyncCache, allItem.get(key).format(**parameterDic))
    return data


def playListOrAlbum(playlist_url: str, playType, track_url, background_tasks):
    """
    播放
    playlist_url:播放列表 或 专辑 的链接
    playType：w+ 播放整个列表或专辑；a+ 添加到播放队列
    track_url: 从此曲目开始播放整个播放列表或专辑
    background_tasks:后台执行对象
    """
    global tidalPlayFlag
    if playType == 'w+':
        tidalPlayFlag = time.time()
    if '/tidal/my/tracks?' in playlist_url:
        playlistInfo = requestAirable(playlist_url.format(1))
    else:
        playlistInfo = requestAirable(playlist_url)
    if int(playlistInfo.get('vit_status')) != 0:
        return playlistInfo
    pages = playlistInfo.get('content', {}).get('pagination', {}).get('pages', {}).get('values', [])  # 总页数
    # 遍历当前页歌曲 如果未找到播放链接则直接返回提示
    beforeData = []  # [{'tracks':list,'info':list}]  #保存前段部分
    afterData = []  # [{'tracks':list,'info':list}]  # 保存后段部分
    tempUrls = []  # 保存剩余部分
    flag = False  # 是否等于从此曲播放
    # 1.整专辑播放，加载第一页到播放列表，其他页后台加载
    # 2.从此曲目播放，for循环找到该曲目后，其余部分后台加载
    for page in pages:
        if not flag:
            if page != 1:
                if '/tidal/my/tracks?' in playlist_url:  # 我的收藏--曲目  url有区别
                    playlistInfo = requestAirable(playlist_url.format(page))
                else:
                    playlistInfo = requestAirable(f'{playlist_url}?p={page}')
            saveTrackInfo(playlistInfo)
            entries = playlistInfo.get('content', {}).get('entries', [])
            for entrie in entries:
                if 'track' not in entrie.get('id'):
                    continue
                if playlistInfo.get('type') == 'album':  # album 的年份在外面
                    if entrie.get('album'):
                        entrie['album']['release'] = playlistInfo.get('release')
                url = entrie.get('url')
                if url != track_url and not flag and url:
                    beforeData.append({'track': f'{vit_prefix_tidal}{url}', 'info': getTrackInfo(entrie)})
                elif (url == track_url or flag) and url:
                    flag = True
                    afterData.append({'track': f'{vit_prefix_tidal}{url}', 'info': getTrackInfo(entrie)})
            if track_url is None:
                flag = True
        else:
            if '/tidal/my/tracks?' in playlist_url:
                tempUrls.append(playlist_url.format(page))
            else:
                tempUrls.append(f'{playlist_url}?p={page}')
    if track_url:  # 从此曲目播放
        if afterData:
            save_song_info_and_play(afterData, playType)
            background_tasks.add_task(playListOrAlbumThreading, tempUrls, beforeData, tidalPlayFlag)
        else:
            return {'vit_status': 4, 'vit_message': "403"}
    else:  # 整专辑播放，执行播放或加载第一页
        if beforeData:
            save_song_info_and_play(beforeData, playType)
            background_tasks.add_task(playListOrAlbumThreading, tempUrls, [], tidalPlayFlag)
        else:
            return {'vit_status': 4, 'vit_message': "403"}
    return {'vit_status': 0, 'vit_message': playlist_url}


def playListOrAlbumThreading(urls, trackDatas, PlayFlag):
    """
    线程添加播放列表到播放器
    """
    global tidalPlayFlag
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
    if tidalPlayFlag == PlayFlag:
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
            trackDic.append({'track': f'{vit_prefix_tidal}{url}', 'info': getTrackInfo(entrie)})


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
    with open(tidal_m3u8_path, mode='w+', encoding='utf8') as f3:
        f3.write('\n'.join(track_all))
    if playType == 'w+':
        # 修改开始播放默认第一首歌 也就是客户端选中的那首歌 这样才不会在随机播放的模式下无法播放客户端选中的歌曲
        # os.system(f'{COMMAND_MPC} clear > /dev/null 2>&1 && {COMMAND_MPC} load {tidal_m3u8_path}  > /dev/null 2>&1 && {COMMAND_MPC} play 1 > /dev/null 2>&1')
        os.popen(f'{COMMAND_MPC} clear > /dev/null 2>&1 && {COMMAND_MPC} load {tidal_m3u8_path}  > /dev/null 2>&1 && {COMMAND_MPC} play 1 > /dev/null 2>&1')
    elif playType == 'a+':
        os.popen(f'{COMMAND_MPC} load {tidal_m3u8_path}  > /dev/null 2>&1')


def getTrackInfo(infoJson: dict):
    """
    infoJson：曲目的json数据
    注意：字符串':'后面有空格
    """
    tarckId = infoJson.get('id', ['', '', None])
    if tarckId[0] != 'tidal' or tarckId[1] != 'track' or tarckId[2] is None:
        return ''
    release = infoJson.get('album', {}).get('release')
    if release:
        Date = time.strftime('%Y-%m-%d', time.localtime(release))
    else:
        Date = '-'
    strTemp = f"song_begin: {vit_prefix_tidal}{infoJson.get('url', '')}\n" + \
              f"Title: {infoJson.get('title', '')}\n" + \
              f"Artist: {infoJson.get('artist', {}).get('title', '')}\n" + \
              f"Album: {infoJson.get('album', {}).get('title', '')}\n" + \
              f"Date: {Date}\n" + \
              f"Cover: {infoJson.get('images', [''])[-1].get('url', '')}\n" + \
              f"CoverPreview: {infoJson.get('images', [''])[0].get('url', '')}\n" + \
              f"duration: {infoJson.get('duration', '0')}\n" + \
              f"Time: {infoJson.get('duration', '0')}\n" + \
              f"song_end\n"
    return strTemp
