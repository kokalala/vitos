cacheDefaultTime = 60 * 60 * 48  # 默认缓存时间
cacheListLimit = 1000  # 缓存队列大小
app_song_info = '/mnt/mpd/app_song_info'
qobuz_m3u8_path = "/tmp/vitos_qobuz_list.m3u8"
vit_prefix = "http://online.silentangel.audio/qobuz/"
# vit_prefix = "http://127.0.0.1:6599/qobuz/track/"
COMMAND_MPC = 'mpc'  # mpc的路径
thunder_aes_cbc128 = "thunder_aes_cbc128"  # 密码加解密
# from api import spoofbuz
info_path = '/mnt/settings/login_info.txt'
app_id_info = '/srv/py/qobuz/qobuz_app_id'
baseUrl = 'http://www.qobuz.com/api.json/0.2'
cacheMainDir = "/mnt/streaming_cache"
cacheQobuzDir = "/mnt/streaming_cache/qobuz/"  # 缓存文件地址
qobuzGenreIds = "/mnt/streaming_cache/genreids"  # 保存安卓和苹果访问时参数：genre_ids
qobuzServerTime = "/mnt/streaming_cache/qobuz/servertime"
cacheTimeout = 24 * 60 * 60  # 线程缓存失效时间
