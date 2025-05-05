import os
import time
from config import *

def getToken():  # 获取airable token

    locale = "en-US"
    name = "SilentAngel_M1"
    version = "1.0"
    mac = uuid.UUID(int=uuid.getnode()).hex[-12:]
    m1_mac = ":".join([mac[e:e + 2] for e in range(0, 11, 2)])
    salt = ''.join(random.sample(string.ascii_letters + string.digits, 16))
    url = "http://auth.rakoit.com/airable//request_signature.php"
    params = {"uid": uid,
              "locale": locale,
              "did": m1_mac.upper(),
              "salt": salt}
    res = requests.get(url=url, params=params, verify=False,timeout=10)  # 通过auth.rakoit.com获取访问airable的signature
    data = json.loads(res.text)
    signature = data['signature']
    url = "https://meta.airable.io/authentication"
    params = {"device": m1_mac.upper(),
              "name": name,
              "version": version,
              "locale": locale,
              "salt": salt,
              "signature": signature}
    tempTime = time.time()  # 访问meta.airable.io 会出现网络延时，存储访问前时间，避免getAuthorization()获取密码后密码时间超时
    res = requests.get(url=url, params=params, verify=False,timeout=10)  # 获取airable的token
    data = json.loads(res.text)
    data['localTime'] = int(tempTime)
    if data.get('token'):
        writeCacheFile(sessionJson,data)  # 保存文件
        # with open(sessionJson, mode='w+', encoding='utf8') as f3:
        #     f3.write(json.dumps(data))
        #     f3.close()
    return data


def getAuthorization():
    """
    获取airable Authorization信息
    """
    global passwordExpires
    global passwordStr

    if abs(time.time()-passwordExpires) < 10 and passwordStr:  # 判断密码是否有效 8秒内
        #print(passwordStr,int(time.time()-passwordExpires) )
        return passwordStr
    if not os.path.isfile(sessionJson):
        getToken()
    with open(sessionJson, mode='r+', encoding='utf8') as f3:
        try:
            readData = json.loads(f3.read())
            if not readData.get('localTime') or not readData.get('time') or not readData.get('token'):
                delFile(sessionJson)
                readData = {}
        except:
            delFile(sessionJson)
            readData = {}
        f3.close()
    if int(time.time()) + readData.get('localTime',0) - readData.get('time',0) * 2 > 60 * 60 * 3:  # token是否过期
        readData = getToken()
    diff = readData.get('time') - readData.get('localTime')
    token = readData['token']
    url = "http://auth.rakoit.com/airable//request_password.php"
    params = {"uid": uid,
              "token": token,
              "time": int(time.time()) + diff}
    tempTime = time.time()  # 获取访问前时间，避免时间超时后，密码无效
    res = requests.get(url=url, params=params, timeout=10)  #, verify=False
    data = json.loads(res.text)
    password = data['password']
    authorization = token + ":" + password
    authorization_base64 = base64.b64encode(authorization.encode()).decode()
    passwordStr = authorization_base64
    passwordExpires = tempTime
    return authorization_base64


def getUrl(airable_url, isApp=1):
    """
    获取airable 数据
    :param airable_url:
    :param isApp: 1：app操作更新appVisitTime  ，0：获取二级内存
    :return:
    """
    global appVisitTime
    if isApp == 1:
        appVisitTime = time.time()
        # writeCacheFile(runTimePath,"{}".format(time.time()))
    for i in range(5):  # 5次重连
        try:
            authorization = getAuthorization()
            headers = {'Authorization': "Basic " + authorization, "Connection": "close", }
            s = requests.session()
            s.keep_alive = False
            res = None
            res = s.get(url=airable_url, headers=headers, verify=False, timeout=10)
            s.close()
            if res == None:
                return {'vit_status': 4, 'vit_message': '446'}
            # url如果错误，提示："<br /><b>Fatal error</b>:  session_start(): Session id must be a string in <b>/var/www/meta.airable.io/src/Lynchpin/Request.php</b> on line <b>136</b><br />"
            data = json.loads(res.text)
            if data.get('id') == ["airable", "error", "authorization"]:
                getToken()
                continue
            return data
        except:
            logger.exception("what?!")
            continue
    return {'vit_status': 6, 'vit_message': '547', "message": "访问airable服务器异常"}


def tidal_check_data(data):
    """
    校验判断tidal数据
    """
    global isTidalLogin
    global cacheTidalList
    try:
        if data.get('vit_status'):
            return data
        elif data.get('description') == 'Please use your companion app to login':
            data['vit_status'] = 1
            data['vit_message'] = '101'
            setTidalLoginStatus(False)
            clearCache('tidal')
        else:
            if data.get("id") == ["airable", "error", "system"]:  # {"id":["airable","error","system"],"message":"Too many requests."}, {"id":["airable","error","system"],"message":"Exception"} #更改密码
                return {'vit_status': 5, 'vit_message': data.get('message',"")}
            if data.get("id") == ["airable", "error", "authorization"]:  # 登录信息错误
                return {"vit_status": 6, "vit_message": "Invalid signature"}
            data['vit_status'] = 0
            data['vit_message'] = ''
            setTidalLoginStatus(True)
        return data
    except:
        return {'vit_status': 4, 'vit_message': '446'}

def setTidalLoginStatus(status):
    """
    设置tidal的登录状态
    """
    global isTidalLogin
    global cacheTidalList
    if status:
        isTidalLogin = True
    else:
        isTidalLogin = False
        cacheTidalList.clear()

def setAmazonLoginStatus(status):
    """
    设置amazon的登录状态
    """
    global isAmazonLogin
    global cacheAmazonList
    if status:
        isAmazonLogin = True
    else:
        isAmazonLogin = False
        cacheAmazonList.clear()

def amazon_check_data(data):
    """
    校验判断amazon数据
    """
    try:
        if data.get('vit_status'):
            return data
        elif data.get('description') == "Use control app to log in.":
            data['vit_status'] = 1
            data['vit_message'] = '101'
            setAmazonLoginStatus(False)
            clearCache('amazon')
        else:
            if data.get("id") == ["airable", "error", "system"]:  # {"id":["airable","error","system"],"message":"Too many requests."}
                if data.get('message') == 'Exception':  # 搜索没有搜到
                    return {'vit_status': 0, 'vit_message': '0'}
                return {'vit_status': 5, 'vit_message': data.get('message')}
            if data.get("id") == ["airable", "error", "authorization"]:  # 登录信息错误
                return {"vit_status": 6, "vit_message": "Invalid signature"}
            data['vit_status'] = 0
            data['vit_message'] = ''
            setAmazonLoginStatus(True)

        return data
    except:
        return {'vit_status': 4, 'vit_message': '446'}


def writeCacheFile(path, jsonData):
    """
    写文件
    """
    if not Path(os.path.dirname(path)).is_dir():
        os.makedirs(os.path.dirname(path).lower())  # 有同名的文件存在不能创建文件夹，需要改成小写
    if len(os.path.basename(path)) < 255:  # 文件名不能大于255
        with open(path, mode='w+', encoding='utf8') as f:
            f.write(''.join(json.dumps(jsonData)))
            f.close()


def readFile(path):
    """
    读取文件，返回json格式
    """
    data = {}
    #if Path(os.path.dirname(path)).is_dir():
    #print(path)
    if os.path.exists(path):
        with open(path, mode='r+', encoding='utf8') as f:
            try:
                data = json.loads(f.read())
            except:
                pass
            f.close()
    return data


def wiatListAndApp(cachelLis):
    """
    等待cacheList 和 app没有请求后，才返回
    """
    while cachelLis or abs(int(time.time() - appVisitTime)) < 20:  # cacheList有队列 和 有点击动作
        time.sleep(1)


def urlToPath(url, mainDir):
    """
    url转成路径
    """
    if 'https://meta.airable.io/' in url:
        path = os.path.join(mainDir, url.replace('https://meta.airable.io/', ""))
        path = os.path.join(os.path.dirname(path).lower(), os.path.basename(path))
        return path
    else:
        return '/tmp/error'


def isCacheActive(url, mainDir):
    """
    url缓存是否有效，是否过期，默认时间cacheTimeout
    """
    path = urlToPath(url, mainDir)
    if os.path.exists(path):
        mtimeUrl = os.stat(path).st_mtime  # 获取文件的修改时间
        # print(time.time(),mtimeUrl,int(time.time() - mtimeUrl),cacheTimeout)
        if abs(int(time.time() - mtimeUrl)) < cacheTimeout:  # 小于跳过
            return True, path
    return False, path


def getDirSize(dir):
    """
    获取文件夹大小
    """
    size = 0
    for root, dirs, files in os.walk(dir):
        size += sum([os.path.getsize(os.path.join(root, name)) for name in files])
    return size


def delFile(file):
    """
    清除文件
    """
    a = os.popen('rm -f {}'.format(file))
    print('删除缓存路径：', file, a)

def clearCache(platform, day=-1, file="*"):
    """
    清除缓存
    day: -1为全部，day天前的缓存数据

    """
    if day == -1:
        os.popen(f'find {cacheMainDir}/{platform}/ -type f  -name "{file}" -exec rm -rf {{}} \;')
    else:
        os.popen(f'find {cacheMainDir}/{platform}/ -type f -mtime {day} -name "{file}" -exec rm -rf {{}} \;')

def cacheTidalQueue():
    """
    tidal缓存队列线程
    """
    global appVisitTime
    global isTidalLogin
    global cacheTidalList
    while True:
        while not isTidalLogin:
            print('cacheTidalQueue--没有登录')
            time.sleep(3)
        while abs(int(time.time() - appVisitTime)) < 5:  # cacheTidalList有队列 和 有点击动作
            time.sleep(1)
        if cacheTidalList:
            url = cacheTidalList.pop(-1)  # 先进先出
            if not url:
                continue
            path = urlToPath(url, cacheTidalDir)
            if os.path.exists(path):
                mtimeUrl = os.stat(path).st_mtime  # 获取文件的修改时间
                if abs(int(time.time() - mtimeUrl)) < cacheTimeout:  # 小于跳过
                    continue
            try:
                data = tidal_check_data(getUrl(url, isApp=0))
                print("cacheTidalList[{}] pop , time:{}".format(len(cacheTidalList), time.time()))
            except:
                continue
            if data['vit_status'] in [0]:  # 如果获取到数据
                writeCacheFile(path, data)
        time.sleep(random.randint(10, 40) * 0.1)


def getTidalHomepage():  # 获取主页
    """
    tidal缓存队列线程
    """
    print('start get homepage threading')
    global isTidalLogin
    global cacheTidalList
    while True:
        while not isTidalLogin:
            cacheTidalList.clear()
            print('getTidalHomepage--没有登录')
            time.sleep(3)
        sizeTmp = getDirSize(cacheTidalDir)
        print("tidal缓存大小：{}M".format(int(sizeTmp / 1000 / 1000)))
        if sizeTmp > 1000 * 1000 * 1000:  # 缓存大于1G，清除7天前的数据
            clearCache('tidal', day=7)
        for key in allTidalOrder.keys():
            wiatListAndApp(cacheTidalList)
            url = allTidalOrder[key]
            if url == "":
                continue
            status, path = isCacheActive(url, cacheTidalDir)
            print('是否有效(tidal):', status, url)
            if status:
                with open(path, mode='r+', encoding='utf8') as f:
                    tmpData = f.read()
                    f.close()
                    try:
                        data = json.loads(tmpData)
                    except:
                        print(path, 'not is json')
                        continue
            else:
                try:
                    data = tidal_check_data(getUrl(url, isApp=0))
                    if data['vit_status'] == 1:
                        print('tidal没有登录')
                        setTidalLoginStatus(False)
                        clearCache('tidal')
                        break
                    elif data['vit_status'] == 0:
                        writeCacheFile(path, data)
                except Exception:
                    print(Exception)
                    continue
            entries = data.get('content', {}).get('entries', [])
            for item in entries[::-1]:
                itemUrl = item.get('url')
                if itemUrl:
                    if 'album' in itemUrl or 'playlist' in itemUrl:  # 只对播放列表和专辑进行缓存
                        # print("add url:{} to cacheList, time:{}".format(itemUrl,time.time()))
                        if data not in cacheTidalList and len(cacheTidalList) < cacheListLimit:  # 不重复的1000条
                            cacheTidalList.append(itemUrl)
                    elif "/tidal/genre/" in itemUrl:  # 曲风的下一页
                        wiatListAndApp(cacheTidalList)
                        statusGenre, pathGenre = isCacheActive(itemUrl, cacheTidalDir)
                        if statusGenre:
                            with open(pathGenre, mode='r+', encoding='utf8') as f:
                                tmpData = f.read()
                                if len(tmpData) > 100:
                                    dataGenre = json.loads(tmpData)
                                else:
                                    dataGenre = {'vit_status': 2}
                                f.close()
                        else:
                            try:
                                dataGenre = tidal_check_data(getUrl(itemUrl, isApp=0))
                            except Exception:
                                print(Exception)
                                continue
                        if data['vit_status'] == 1:
                            print('tidal没有登录')
                            break
                        if dataGenre['vit_status'] == 0:
                            writeCacheFile(pathGenre, dataGenre)
                            entriesGenre = dataGenre.get('content', {}).get('entries', [])
                            for itemGenre in entriesGenre[::-1]:
                                urlGenre = itemGenre.get('url')
                                if urlGenre:
                                    # print("add url:{} to cacheList, time:{}".format(urlGenre, time.time()))
                                    if data not in cacheTidalList and len(cacheTidalList) < cacheListLimit:  # 不重复的1000条
                                        cacheTidalList.append(urlGenre)
            nextUrl = data.get('content', {}).get('pagination', {}).get('next')
            if nextUrl:
                if nextUrl not in cacheTidalList and len(cacheTidalList) < cacheListLimit:  # 不重复的1000条
                    cacheTidalList.append(url)
            time.sleep(random.randint(20, 50) * 0.1)
        if isTidalLogin:  # 登录状态下才等待120秒
            time.sleep(120)


def cacheAmazonQueue():
    global appVisitTime
    global cacheAmazonList
    global isAmazonLogin
    while True:
        while not isAmazonLogin:
            cacheAmazonList.clear()
            print('cacheAmazonQueue没有登录：',len(cacheAmazonList))
            time.sleep(3)
        while abs(int(time.time() - appVisitTime)) < 5:  # cacheTidalList有队列 和 有点击动作
            time.sleep(1)
        if cacheAmazonList:
            url = cacheAmazonList.pop(-1)  # 先进先出
            if not url:
                continue
            path = urlToPath(url, cacheAmazonDir)
            if os.path.exists(path):
                mtimeUrl = os.stat(path).st_mtime  # 获取文件的修改时间
                if abs(int(time.time() - mtimeUrl)) < cacheTimeout:  # 小于跳过
                    continue
            try:
                data = amazon_check_data(getUrl(url, isApp=0))
                print("cacheAmazonList[{}] pop, time:{}".format(len(cacheAmazonList), time.time()))
            except:
                continue
            if data['vit_status'] in [0]:  # 如果获取到数据
                writeCacheFile(path, data)
        time.sleep(random.randint(10, 40) * 0.1)


def getAmazonHomepage():  # 获取主页
    global cacheAmazonList
    global isAmazonLogin
    print('start get homepage threading')
    while True:
        while not isAmazonLogin:
            print('亚马逊音乐没有登录')
            time.sleep(3)
        sizeTmp = getDirSize(cacheAmazonDir)
        print("amazon缓存大小：{}M".format(int(sizeTmp / 1000 / 1000)))
        if sizeTmp > 1000 * 1000 * 1000:  # 缓存大于1G，清除7天前的数据
            clearCache('amazon', day=7)
        for key in allAmazonOrder.keys():
            wiatListAndApp(cacheAmazonList)
            url = allAmazonOrder[key]
            if url == "":
                continue
            status, path = isCacheActive(url, cacheAmazonDir)
            print('是否有效(amazon):', status, url)
            if status:
                with open(path, mode='r+', encoding='utf8') as f:
                    tmpData = f.read()
                    f.close()
                    try:
                        data = json.loads(tmpData)
                    except:
                        print(path, 'not is json')
                        continue
            else:
                try:
                    data = amazon_check_data(getUrl(url, isApp=0))
                    if data['vit_status'] == 1:  # 未登录，清除队列
                        print('amazon没有登录')
                        setAmazonLoginStatus(False)
                        clearCache('amazon')
                        break
                    elif data['vit_status'] == 0:
                        writeCacheFile(path, data)
                except Exception:
                    print(Exception)
                    continue
            entries = data.get('content', {}).get('entries', [])
            for item in entries[::-1]:
                itemUrl = item.get('url')
                if itemUrl:
                    if 'album' in itemUrl or 'playlist' in itemUrl or 'document' in itemUrl:  # 只对播放列表和专辑进行缓存
                        # print("add url:{} to cacheAmazonList, time:{}".format(itemUrl,time.time()))
                        if data not in cacheAmazonList and len(cacheAmazonList) < cacheListLimit:  # 不重复的1000条
                            cacheAmazonList.append(itemUrl)
            nextUrl = data.get('content', {}).get('pagination', {}).get('next')
            if nextUrl:
                if nextUrl not in cacheAmazonList and len(cacheAmazonList) < cacheListLimit:  # 不重复的1000条
                    cacheAmazonList.append(url)
            time.sleep(random.randint(20, 50) * 0.1)
        if isAmazonLogin:  # 登录状态下才等待120秒
            time.sleep(120)


# 清除3天前日志
try:
    clearCache('logs', day=3, file="*.log.zip")
    sizeTmp = getDirSize(pathLogger)
    print("日志缓存大小：{}M".format(int(sizeTmp / 1000 / 1000)))
    if sizeTmp > 300 * 1000 * 1000:  # 缓存大于300M，清除所有
        clearCache('logs', day=-1,file="*.log.zip")
except:
    pass