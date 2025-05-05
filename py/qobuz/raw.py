'''
    qobuz.api.raw
    ~~~~~~~~~~~~~

    Our base api, all method are mapped like in <endpoint>_<method>
    see Qobuz API on GitHub (https://github.com/Qobuz/api-documentation)

    :part_of: xbmc-qobuz
    :copyright: (c) 2012 by Joachim Basmaison, Cyril Leclerc
    :license: GPLv3, see LICENSE for more details.
'''

import json
import os
import sys
# sys.path.append('/home/lmj/setup/pipeline/Qobuz')#
sys.path.append('/srv/py/')
import time
import math
import hashlib
import socket
import binascii
import urllib
from itertools import cycle
import requests
from qobuz import spoofbuz

# from api import spoofbuz
info_path='/mnt/settings/login_info.txt'
# info_path='./login_info.txt'
socket.timeout = 5
app_song_info = '/mnt/mpd/app_song_info'
vit_prefix = "http://online.silentangel.audio/qobuz/"
_loglevel = 3
def debug(s):
    if _loglevel >= 2:
        print("%s" %s, file=sys.stderr)
def warn(s):
    if _loglevel >= 3:
        print("%s" %s, file=sys.stderr)

class RawApi(object):

    def __init__(self, appid, configvalue):

        # if appid and configvalue:
        #     # self.configvalue = configvalue
        #     # self.appid = appid
        #     self.__set_s4()
        # else:
        #     self.spoofer = spoofbuz.Spoofer()
        #     self.appid = self.spoofer.getAppId()
        #     self.appid=appid
        self.appid=appid
        self.version = '0.2'
        self.baseUrl = 'http://www.qobuz.com/api.json/'
        self.user_auth_token = None
        self.user_id = None
        self.error = None
        self.status_code = None
        self._baseUrl = self.baseUrl + self.version
        self.session = requests.Session()
        self.error = None

    def _api_error_string(self, request, url='', params={}, json=''):
        return '{reason} (code={status_code})\n' \
                'url={url}\nparams={params}' \
                '\njson={json}'.format(reason=request.reason, status_code=self.status_code,
                                       url=url,
                                       params=str(['%s: %s' % (k, v) for k, v in params.items() ]),
                                       json=str(json))

    # 接口参数检查 mandatory是必须传入的参数，allowed是可以传入的参数
    def _check_ka(self, ka, mandatory, allowed=[]):
        '''Checking parameters before sending our request
        - if mandatory parameter is missing raise error
        - if a given parameter is neither in mandatory or allowed
        raise error
        '''
        # 发送请求前检查参数
        # -如果缺少强制参数，则引发错误
        # -如果给定参数既不是强制的也不是允许的
        # 上升误差
        for label in mandatory:
            if not label in ka:#如果传入的参数不包含必须的参数则抛出异常
                raise Exception("Qobuz: missing parameter [%s]" % label)
        for label in ka:
            if label not in mandatory and label not in allowed:#如果传入的参数不是不须的也不是允许的
                raise Exception("Qobuz: invalid parameter [%s]" % label)

    def __set_s4(self):
        '''appid and associated secret is for this app usage only
        Any use of the API implies your full acceptance of the
        General Terms and Conditions
        (http://www.qobuz.com/apps/api/QobuzAPI-TermsofUse.pdf)
        '''
        s3b = self.configvalue.encode('ASCII')
        s3s = binascii.a2b_base64(s3b)
        bappid = self.appid.encode('ASCII')
        a = cycle(bappid)
        b = zip(s3s, a)
        self.s4 = b''.join((x ^ y).to_bytes(1, byteorder='big') for (x, y) in b)
        #print("S4: %s"% self.s4.decode('ASCII'), file=sys.stderr)
        
    def __unset_s4(self, id, sec):
        a = cycle(id)
        b = zip(sec, a)
        bs4 = b''.join((x ^ y).to_bytes(1, byteorder='big') for (x, y) in b)
        value = binascii.b2a_base64(bs4)
        return value

    def _api_request(self, params, uri, **opt):
        '''Qobuz API HTTP get request
            Arguments:
            params:    parameters dictionary
            uri   :    service/method
            opt   :    Optionnal named parameters
                        - noToken=True/False

            Return None if something went wrong
            Return raw data from qobuz on success as dictionary

            * on error you can check error and status_code

            Example:

                ret = api._api_request({'username':'foo',
                                  'password':'bar'},
                                 'user/login', noToken=True)
                print('Error: %s [%s]' % (api.error, api.status_code))

            This should produce something like:
            Error: [200]
            Error: Bad Request [400]
        '''
        self.error = ''
        self.status_code = None
        url = self._baseUrl + uri
        # print(url)
        useToken = False if (opt and 'noToken' in opt) else True
        headers = {
            "User-Agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:67.0) Gecko/20100101 Firefox/67.0"
        }
        if useToken and self.user_auth_token:
            headers['X-User-Auth-Token'] = self.user_auth_token
        headers['X-App-Id'] = self.appid
        r = None
        #debug("POST %s params %s headers %s" % (url, params, headers))
        try:
            r = self.session.post(url, data=params, headers=headers)
        except:
            self.error = 'Post request fail'
            warn(self.error)
            return None
        self.status_code = int(r.status_code)
        if self.status_code != 200:
            # print(r.text)
            self.error = self._api_error_string(r, url, params)
            warn(self.error)
            return None
        if not r.content:
            self.error = 'Request return no content'
            warn(self.error)
            return None

        '''Retry get if connexion fail'''
        try:
            response_json = r.json()
        except Exception as e:
            warn('Json loads failed to load... retrying!\n{}', repr(e))
            try:
                response_json = r.json()
            except:
                self.error = "Failed to load json two times...abort"
                warn(self.error)
                return None
        status = None
        try:
            status = response_json['status']
        except:
            pass
        if status == 'error':
            self.error = self._api_error_string(r, url, params,
                                                response_json)
            warn(self.error)
            return None
        return response_json

    def set_user_data(self, user_id, user_auth_token):
        if not (user_id and user_auth_token):
            raise Exception("Qobuz: missing argument uid|token")
        self.logged_on = time.time()

    def logout(self):
        self.user_auth_token = None
        self.user_id = None
        self.logged_on = None

    def user_login(self, **ka):
        self._check_ka(ka, ['username', 'password'], ['email'])
        data = self._api_request(ka, '/user/login', noToken=True)
        if not data or not 'user' in data or not 'credential' in data['user'] \
           or not 'id' in data['user'] \
           or not 'parameters' in data['user']['credential']:
            warn("/user/login returns %s" % data)
            self.logout()
            return None
        if not data["user"]["credential"]["parameters"]:
            warn("Free accounts are not eligible to download tracks.")
            return None
        self.user_id = data['user']['id']
        self.user_auth_token = data["user_auth_token"]
        self.label = data["user"]["credential"]["parameters"]["short_label"]
        debug("Membership: {}".format(self.label))
        data['user']['email'] = ''
        data['user']['firstname'] = ''
        data['user']['lastname'] = ''
        self.setSec()

        return data

    def setSec(self):
        global _loglevel
        savedlevel = _loglevel
        _loglevel = 1
        for value in self.spoofer.getSecrets().values():
            self.s4 = value.encode('utf-8')
            if self.userlib_getAlbums(sec=self.s4) is not None:
                #debug("SECRET [%s]"%self.s4)
                _loglevel = savedlevel
                return


    def user_update(self, **ka):
        self._check_ka(ka, [], ['player_settings'])
        return self._api_request(ka, '/user/update')

    def track_get(self, **ka):
        self._check_ka(ka, ['track_id'])
        return self._api_request(ka, '/track/get')

    def track_getFileUrl(self, intent="stream", **ka):
        self._check_ka(ka, ['format_id', 'track_id'])
        ts = str(time.time())
        track_id = str(ka['track_id'])
        fmt_id = str(ka['format_id'])
        stringvalue = 'trackgetFileUrlformat_id' + fmt_id \
                      + 'intent' + intent \
                      + 'track_id' + track_id + ts
        stringvalue = stringvalue.encode('ASCII')


        stringvalue  += self.s4
        rq_sig = str(hashlib.md5(stringvalue).hexdigest())
        params = {'format_id': fmt_id,
                  'intent': intent,
                  'request_ts': ts,
                  'request_sig': rq_sig,
                  'track_id': track_id
                  }
        return self._api_request(params, '/track/getFileUrl')

    def userlib_getAlbums(self, **ka):
        ts = str(time.time())
        r_sig = "userLibrarygetAlbumsList" + str(ts) + str(ka["sec"])
        r_sig_hashed = hashlib.md5(r_sig.encode("utf-8")).hexdigest()
        params = {
            "app_id": self.appid,
            "user_auth_token": self.user_auth_token,
            "request_ts": ts,
            "request_sig": r_sig_hashed,
        }
        return self._api_request(params, '/userLibrary/getAlbumsList')

    def track_search(self, **ka):
        self._check_ka(ka, ['query'], ['limit'])
        return self._api_request(ka, '/track/search')

    def catalog_search(self, **ka):

        """
        搜索：
        必须参数：query 搜索的关键字 可以是单曲 歌手 或则是播放列表和专辑
        可选参数：
        type：
        offset：分页时使用
        limit:返回的数据量
        """
        # type may be 'tracks', 'albums', 'artists' or 'playlists'
        self._check_ka(ka, ['query'], ['type', 'offset', 'limit'])
        return self._api_request(ka, '/catalog/search')

    def catalog_getFeatured(self, **ka):
        return self._api_request(ka, '/catalog/getFeatured')

    def catalog_getFeaturedTypes(self, **ka):
        return self._api_request(ka, '/catalog/getFeaturedTypes')
    
    def track_resportStreamingStart(self, track_id):

        # Any use of the API implies your full acceptance
        # of the General Terms and Conditions
        # (http://www.qobuz.com/apps/api/QobuzAPI-TermsofUse.pdf)
        params = {'user_id': self.user_id, 'track_id': track_id}
        return self._api_request(params, '/track/reportStreamingStart')

    def track_resportStreamingEnd(self, track_id, duration):
        duration = math.floor(int(duration))
        if duration < 5:
            warn(self, 'Duration lesser than 5s, abort reporting')
            return None
        # @todo ???
        user_auth_token = ''  # @UnusedVariable
        try:
            user_auth_token = self.user_auth_token  # @UnusedVariable
        except:
            warn('No authentification token')
            return None
        params = {'user_id': self.user_id,
                  'track_id': track_id,
                  'duration': duration
                  }
        return self._api_request(params, '/track/reportStreamingEnd')

    def album_get(self, **ka):
        self._check_ka(ka, ['album_id'])
        return self._api_request(ka, '/album/get')

    def album_getFeatured(self, **ka):
        self._check_ka(ka, [], ['type', 'genre_ids', 'limit', 'offset'])
        return self._api_request(ka, '/album/getFeatured')

    def purchase_getUserPurchases(self, **ka):
        self._check_ka(ka, [], ['order_id', 'order_line_id', 'flat', 'limit',
                                'offset'])
        return self._api_request(ka, '/purchase/getUserPurchases')

    def search_getResults(self, **ka):
        self._check_ka(ka, ['query', 'type'], ['limit', 'offset'])
        return self._api_request(ka, '/search/getResults')

    def favorite_getUserFavorites(self, **ka):
        self._check_ka(ka, [], ['user_id', 'type', 'limit', 'offset'])
        return self._api_request(ka, '/favorite/getUserFavorites')

    def favorite_create(self, **ka):
        mandatory = ['artist_ids', 'album_ids', 'track_ids']
        found = None
        for label in mandatory:
            if label in ka:
                found = label
        if not found:
           raise Exception("Qobuz: missing parameter: artist_ids|albums_ids|track_ids")
        return self._api_request(ka, '/favorite/create')

    def favorite_delete(self, **ka):
        mandatory = ['artist_ids', 'album_ids', 'track_ids']
        found = None
        for label in mandatory:
            if label in ka:
                found = label
        if not found:
            raise Exception("Qobuz: missing parameter: artist_ids|albums_ids|track_ids")
        return self._api_request(ka, '/favorite/delete')

    def playlist_get(self, **ka):
        self._check_ka(ka, ['playlist_id'], [ 'limit', 'offset','extra'])#参数 'extra', 可以不用传入。
        return self._api_request(ka, '/playlist/get')

    def playlist_getFeatured(self, **ka):
        # type is 'last-created' or 'editor-picks'
        self._check_ka(ka, ['type'], ['genre_id', 'limit', 'offset','tags'])
        return self._api_request(ka, '/playlist/getFeatured')

    def playlist_getUserPlaylists(self, **ka):
        self._check_ka(ka, [], ['user_id', 'username', 'order', 'offset', 'limit'])
        if not 'user_id' in ka and not 'username' in ka:
            ka['user_id'] = self.user_id
        return self._api_request(ka, '/playlist/getUserPlaylists')

    def playlist_addTracks(self, **ka):
        self._check_ka(ka, ['playlist_id', 'track_ids'])
        return self._api_request(ka, '/playlist/addTracks')

    def playlist_deleteTracks(self, **ka):
        self._check_ka(ka, ['playlist_id'], ['playlist_track_ids'])
        return self._api_request(ka, '/playlist/deleteTracks')

    def playlist_subscribe(self, **ka):
        self._check_ka(ka, ['playlist_id'], ['playlist_track_ids'])
        return self._api_request(ka, '/playlist/subscribe')

    def playlist_unsubscribe(self, **ka):
        self._check_ka(ka, ['playlist_id'])
        return self._api_request(ka, '/playlist/unsubscribe')

    def playtracks_countlist_create(self, **ka):
        self._check_ka(ka, ['name'], ['is_public','description',
                                      'is_collaborative', 'tracks_id', 'album_id'])
        if not 'is_public' in ka:
            ka['is_public'] = True
        if not 'is_collaborative' in ka:
            ka['is_collaborative'] = False
        return self._api_request(ka, '/playlist/create')


    def playlist_delete(self, **ka):
        self._check_ka(ka, ['playlist_id'])
        return self._api_request(ka, '/playlist/delete')

    def playlist_update(self, **ka):
        self._check_ka(ka, ['playlist_id'], ['name', 'description',
                                             'is_public', 'is_collaborative', 'tracks_id'])
        return self._api_request(ka, '/playlist/update')

    def playlist_getPublicPlaylists(self, **ka):
        self._check_ka(ka, [], ['type', 'limit', 'offset'])
        return self._api_request(ka, '/playlist/getPublicPlaylists')

    def artist_getSimilarArtists(self, **ka):
        self._check_ka(ka, ['artist_id'], ['limit', 'offset'])
        return self._api_request(ka, '/artist/getSimilarArtists')

    def artist_get(self, **ka):
        self._check_ka(ka, ['artist_id'], ['extra', 'limit', 'offset'])
        return self._api_request(ka, '/artist/get')

    def genre_list(self, **ka):
        self._check_ka(ka, [], ['parent_id', 'limit', 'offset'])
        # return self.td_qobuz_api_request(ka, '/genre/list')
        return self._api_request(ka, '/genre/list')

    def label_list(self, **ka):
        self._check_ka(ka, [], ['limit', 'offset'])
        return self._api_request(ka, '/label/list')

    def article_listRubrics(self, **ka):
        self._check_ka(ka, [], ['extra', 'limit', 'offset'])
        return self._api_request(ka, '/article/listRubrics')

    def article_listLastArticles(self, **ka):
        self._check_ka(ka, [], ['rubric_ids', 'offset', 'limit'])
        return self._api_request(ka, '/article/listLastArticles')

    def article_get(self, **ka):
        self._check_ka(ka, ['article_id'])
        return self._api_request(ka, '/article/get')
    def collection_getAlbums(self, **ka):
        self._check_ka(ka, [], ['source', 'artist_id', 'query',
                                'limit', 'offset'])
        return self._api_request(ka, '/collection/getAlbums')

    def collection_getArtists(self, **ka):
        self._check_ka(ka, [], ['source', 'query',
                                'limit', 'offset'])
        return self._api_request(ka, '/collection/getArtists')

    def collection_getTracks(self, **ka):
        self._check_ka(ka, [], ['source', 'artist_id', 'album_id', 'query',
                                'limit', 'offset'])
        return self._api_request(ka, '/collection/getTracks')
    def session_start(self,**ka):
        self._check_ka(ka,[])
        ts = str(time.time())
        params = {
                "request_ts": ts,
                "request_sig": "51e7c9b5dce64f60e24cdfe2b62abcb6",
                "profile": "qbz-1"
            }
        return self._api_request(params,'/session/start')

    def featured_playlist_tags(self, **ka):
        return self._api_request(ka, '/playlist/getTags')

    def feature_albums(self,**ka):
        return self._api_request(ka,'/featured/albums')

####################################################################################################
    def td_qobuz_track_get(self, parameter):
        ka=self.td_qobuz_parameter_dic(parameter)
        status=self.td_qobuz_check_ka(ka, ['track_id'])
        if status=='pass':
            return self.td_qobuz_api_request(ka, '/track/get')
        else:
            return status

    def td_qobuz_track_search(self,parameter):
        ka=self.td_qobuz_parameter_dic(parameter)
        if 'limit' not in ka:
            ka['limit']=30
        status=self.td_qobuz_check_ka(ka, ['query'], ['limit'])
        if status=='pass':
            return self._api_request(ka, '/track/search')
        else:
            return status
    def td_qobuz_album_search(self,parameter):
        ka=self.td_qobuz_parameter_dic(parameter)
        if 'limit' not in ka:
            ka['limit']=30
        status=self.td_qobuz_check_ka(ka, ['query'], ['limit'])
        if status=='pass':
            return self._api_request(ka, '/album/search')
        else:
            return status
    def td_qobuz_artist_search(self,parameter):
        ka=self.td_qobuz_parameter_dic(parameter)
        if 'limit' not in ka:
            ka['limit']=30
        status=self.td_qobuz_check_ka(ka, ['query'], ['limit'])
        if status=='pass':
            return self._api_request(ka, '/artist/search')
        else:
            return status

    def td_qobuz_playlist_search(self,parameter):
        ka=self.td_qobuz_parameter_dic(parameter)
        if 'limit' not in ka:
            ka['limit']=30
        self.td_qobuz_check_ka(ka, ['query'], ['limit'])
        return self._api_request(ka, '/playlist/search')

    def td_qobuz_Logout(self):
        self.user_auth_token = None
        self.user_id = None
        self.logged_on = None

        info = ''
        skip_tidal = False
        try:
            os.system('mpc playlistdel http://online.silentangel.audio/qobuz > /dev/null 2>&1')
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


        if os.path.exists(info_path):
            try:
                os.remove(info_path)
                return json.dumps({"vit_status": 0, "vit_message": ""})
            except:
                return json.dumps({"vit_status": 1, "vit_message": '104'})

        else:
            return json.dumps({"vit_status": 1, "vit_message": '101'})

    def td_qobuz_artist_get(self, parameter):
        ka = self.td_qobuz_parameter_dic(parameter)
        if 'limit' not in ka:
            ka['limit']=30
        if 'offset' not in ka:
            ka['offset']=0
        status=self.td_qobuz_check_ka(ka, ['artist_id'], ['extra', 'limit', 'offset'])
        if status=='pass':
            return self.td_qobuz_api_request(ka, '/artist/get')
        else:
            return status
    def td_qobuz_user_favorite_ids(self,parameter):
        ka =self.td_qobuz_parameter_dic(parameter=parameter)
        if 'limit' not in ka:
            ka['limit']=5000
        ka['offset']=0
        if not 'user_id' in ka:
            ka['user_id'] = self.user_id
        status=self.td_qobuz_check_ka(ka,['user_id'],['limit', 'offset'])
        if status:
             data=self.td_qobuz_api_request(ka,'/favorite/getUserFavoriteIds')
             data['user_id']=ka['user_id']
             return data
        else:
            return status
    def td_qobuz_favorite_create(self, parameter):
        ka = self.td_qobuz_parameter_dic(parameter)
        mandatory = ['artist_ids', 'album_ids', 'track_ids']
        found = None
        for label in mandatory:
            if label in ka:
                found = label
        if not found:
           return json.dumps({"vit_status":2,'vit_message':"201"})
        return self.td_qobuz_api_request(ka, '/favorite/create')

    def td_qobuz_favorite_delete(self, parameter):
        ka = self.td_qobuz_parameter_dic(parameter)
        mandatory = ['artist_ids', 'album_ids', 'track_ids']
        found = None
        for label in mandatory:
            if label in ka:
                found = label
        if not found:
            return json.dumps({"vit_status": 2, 'vit_message': "201"})
        return self.td_qobuz_api_request(ka, '/favorite/delete')

    def td_qobuz_favorite_getUserFavorites(self,parameter):
        ka = self.td_qobuz_parameter_dic(parameter)
        if 'limit' not in ka:
            ka['limit']=30
        if 'offset' not in ka:
            ka['offset']=0
        if 'user_id' not in ka:
            ka['user_id']=self.user_id
        status=self.td_qobuz_check_ka(ka, [], ['user_id', 'type', 'limit', 'offset'])

        if status=='pass':
            return self.td_qobuz_api_request(ka, '/favorite/getUserFavorites')
        else:
            return status
    def td_qobuz_playlist_addTracks(self, parameter):
        ka = self.td_qobuz_parameter_dic(parameter)
        status=self.td_qobuz_check_ka(ka, ['playlist_id', 'track_ids'])
        if status=='pass':
            return self.td_qobuz_api_request(ka, '/playlist/addTracks')
        else:
            return status
    def td_qobuz_playlist_deleteTracks(self, parameter):
        ka = self.td_qobuz_parameter_dic(parameter)
        status=self.td_qobuz_check_ka(ka, ['playlist_id'], ['playlist_track_ids'])
        if status=='pass':
            return self.td_qobuz_api_request(ka, '/playlist/deleteTracks')
        else:
            return status
    def td_qobuz_playlist_delete(self, parameter):
        ka = self.td_qobuz_parameter_dic(parameter)
        status=self.td_qobuz_check_ka(ka, ['playlist_id'])
        if status=='pass':
            return self.td_qobuz_api_request(ka, '/playlist/delete')
        else:
            return status
    def td_qobuz_playlist_update(self,parameter):
        ka = self.td_qobuz_parameter_dic(parameter)
        status=self.td_qobuz_check_ka(ka, ['playlist_id'], ['name', 'description',
                                             'is_public', 'is_collaborative', 'tracks_id'])
        if status=='pass':
            return self.td_qobuz_api_request(ka, '/playlist/update')
        else:
            return status
    def td_qobuz_album_get(self, parameter):
        ka = self.td_qobuz_parameter_dic(parameter)
        status=self.td_qobuz_check_ka(ka, ['album_id'])
        if status=='pass':
            return self.td_qobuz_api_request(ka, '/album/get')
        else:
            return status
    def td_qobuz_catalog_search(self, parameter):

        """
        搜索：
        必须参数：query 搜索的关键字 可以是单曲 歌手 或则是播放列表和专辑
        可选参数：
        type：
        offset：分页时使用
        limit:返回的数据量
        """
        # type may be 'tracks', 'albums', 'artists' or 'playlists'
        ka = self.td_qobuz_parameter_dic(parameter)
        if 'limit' not in ka:
            ka['limit']=30
        if 'offset' not in ka:
            ka['offset']=0
        status=self.td_qobuz_check_ka(ka, ['query'], ['type', 'offset', 'limit'])
        if status=='pass':
            return self.td_qobuz_api_request(ka, '/catalog/search')
        else:
            return status
    def td_qobuz_track_getFileUrl(self,parameter, intent="stream"):
        ka = self.td_qobuz_parameter_dic(parameter)
        if 'format_id' not in ka:
            ka['format_id']=27
        status=self.td_qobuz_check_ka(ka, ['format_id', 'track_id'])
        if status=='pass':
            ts = str(time.time())
            track_id = str(ka['track_id'])
            fmt_id = str(ka['format_id'])
            stringvalue = 'trackgetFileUrlformat_id' + fmt_id \
                          + 'intent' + intent \
                          + 'track_id' + track_id + ts
            stringvalue = stringvalue.encode('ASCII')


            stringvalue  += self.s4
            rq_sig = str(hashlib.md5(stringvalue).hexdigest())
            params = {'format_id': fmt_id,
                      'intent': intent,
                      'request_ts': ts,
                      'request_sig': rq_sig,
                      'track_id': track_id
                      }
            return self.td_qobuz_api_request(params, '/track/getFileUrl')
        else:
            return status


    def td_qobuz_catalog_getFeatured(self, parameter):
        ka = self.td_qobuz_parameter_dic(parameter)
        return self.td_qobuz_api_request(ka, '/catalog/getFeatured')


    def td_qobuz_catalog_getFeaturedTypes(self, parameter):
        ka = self.td_qobuz_parameter_dic(parameter)
        return self.td_qobuz_api_request(ka, '/catalog/getFeaturedTypes')


    def td_qobuz_featured_playlist_tags(self, parameter):
        ka = self.td_qobuz_parameter_dic(parameter)
        return self.td_qobuz_api_request(ka, '/playlist/getTags')

    def td_qobuz_playlist_get(self, parameter):
        ka = self.td_qobuz_parameter_dic(parameter)
        if 'limit' not in ka:
            ka['limit']=30
        if 'offset' not in ka:
            ka['offset']=0
        status=self.td_qobuz_check_ka(ka, ['playlist_id'], ['limit', 'offset', 'extra'])  # 参数 'extra', 可以不用传入。
        if status=='pass':
            return self.td_qobuz_api_request(ka, '/playlist/get')
        else:
            return status
    def td_qobuz_playlist_subscribe(self, parameter):
        ka = self.td_qobuz_parameter_dic(parameter)
        status=self.td_qobuz_check_ka(ka, ['playlist_id'], ['playlist_track_ids'])
        if status=='pass':
            return self.td_qobuz_api_request(ka, '/playlist/subscribe')
        else:
            return status

    def td_qobuz_playlist_unsubscribe(self,parameter):
        ka=self.td_qobuz_parameter_dic(parameter)
        status=self.td_qobuz_check_ka(ka, ['playlist_id'])
        if status=='pass':
            return self.td_qobuz_api_request(ka, '/playlist/unsubscribe')
        else:
            return status
    def td_qobuz_playlist_getUserPlaylists(self, parameter):
        ka = self.td_qobuz_parameter_dic(parameter)
        if 'limit' not in ka:
            ka['limit']=30
        if 'offset' not in ka:
            ka['offset']=0
        self.td_qobuz_check_ka(ka, [], ['user_id', 'username', 'order', 'offset', 'limit'])
        if not 'user_id' in ka :
            ka['user_id'] = self.user_id
        return self.td_qobuz_api_request(ka, '/playlist/getUserPlaylists')

    def td_qobuz_playlist_create(self, parameter):
        ka = self.td_qobuz_parameter_dic(parameter)
        if not 'is_public' in ka:
            ka['is_public'] = "false"
        if not 'is_collaborative' in ka:
            ka['is_collaborative'] = "false"
        status=self.td_qobuz_check_ka(ka, ['name'], ['description', 'is_public', 'is_collaborative', 'tracks_id', 'album_id'])

        if status=='pass':
            return self.td_qobuz_api_request(ka, '/playlist/create')
        else:
            return status
    def td_qobuz_genre_list(self,parameter):
        ka = self.td_qobuz_parameter_dic(parameter)
        if 'limit' not in ka:
            ka['limit']=30
        if 'offset' not in ka:
            ka['offset']=0
        status=self.td_qobuz_check_ka(ka, [], ['parent_id', 'limit', 'offset'])
        if status=='pass':
            return self.td_qobuz_api_request(ka, '/genre/list')
        else:
            return status


    def td_qobuz_api_request(self, params, uri, **opt):
        '''Qobuz API HTTP get request
            Arguments:
            params:    parameters dictionary
            uri   :    service/method
            opt   :    Optionnal named parameters
                        - noToken=True/False

            Return None if something went wrong
            Return raw data from qobuz on success as dictionary

            * on error you can check error and status_code

            Example:

                ret = api._api_request({'username':'foo',
                                  'password':'bar'},
                                 'user/login', noToken=True)
                print('Error: %s [%s]' % (api.error, api.status_code))

            This should produce something like:
            Error: [200]
            Error: Bad Request [400]
        '''
        self.error = ''
        self.status_code = None
        url = self._baseUrl + uri
        # print(url)
        useToken = False if (opt and 'noToken' in opt) else True
        headers = {
            "User-Agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:67.0) Gecko/20100101 Firefox/67.0"
        }
        if useToken and self.user_auth_token:
            headers['X-User-Auth-Token'] = self.user_auth_token
        headers['X-App-Id'] = self.appid
        r = None
        #debug("POST %s params %s headers %s" % (url, params, headers))
        try:
            r = self.session.get(url, params=params, headers=headers)
            # if uri in ["/album/get"]:
            #     r = self.session.get(url, params=params, headers=headers)
            # else:
            #     r = self.session.post(url, data=params, headers=headers)
        except:
            #连接请求失败
            return ('{"vit_status":4,"vit_message":"444"}')

        self.status_code = int(r.status_code)
        if self.status_code != 200:
            #如果服务器错误则返回对应的状态码
            return {"vit_status":4,"vit_message":str(self.status_code)}
        try:
            response_json = r.json()
        except Exception as e:
            try:
                response_json = r.json()
            except:
                return {"vit_status":4,"vit_message":'446'}#获取不到json数据
        status = None
        try:
            status = response_json['status']
        except:
            pass
        if status == 'error':
            return {"vit_status": 4, "vit_message": '447'}#返回的是错误的数据
        response_json['vit_status']=0
        response_json['vit_message']=''
        return response_json





    def td_qobuz_check_ka(self, ka, mandatory, allowed=[]):
        '''Checking parameters before sending our request
        - if mandatory parameter is missing raise error
        - if a given parameter is neither in mandatory or allowed
        raise error
        '''
        # 发送请求前检查参数
        # -如果缺少必须参数，则返回相应的状态和消息
        #  -如果给定参数既不是必须的也不是允许的，返回状态信息
        for label in mandatory:
            if not label in ka:#如果传入的参数不包含必须的参数则返回相应的状态和信息
                if label=='username':
                    message={"vit_status":2,'vit_message':'201'}
                    return message
                elif label=='password':
                    message={"vit_status":2,'vit_message':'202'}
                    return message
                else:
                    vit_message=200+int(mandatory.index(label)+1)
                    message={"vit_status":2,'vit_message':str(vit_message)}
                    return message

        # for label in ka:
        #     if label not in mandatory and label not in allowed:#如果传入的参数不是不须的也不是允许的也返回相应的状态和信息
        #         return json.dumps({"vit_status":2,"vit_message":'200'})
        return 'pass'

    def td_qobuz_maybe_login(self):  # 用户已登陆就从登陆信息中获取请求所需要的关键字段，

        if os.path.exists(info_path):  # 如果文件存在则表示用户登陆过
            try:
                with open(info_path)as f:
                    data = json.load(f)
            except:
                os.remove(info_path)
                return json.dumps('{"vit_status":4,"vit_message":"44"}')


            if not data['userData']["user"]["credential"]["parameters"]:
                self.user_id = data['userData']['user']['id']
                self.user_auth_token = data['userData']["user_auth_token"]
                self.s4 = data['userData'].get('s4').encode()
                self.appid = data['userData']['appid']
                # return json.dumps({"vit_status": 1, "vit_message": "104"})  # 非订阅用户。
            else:

                self.label = data['userData']["user"]["credential"]["parameters"]["short_label"]
                self.user_id = data['userData']['user']['id']
                self.user_auth_token = data['userData']["user_auth_token"]
                self.s4 = data['userData'].get('s4').encode()
                self.appid = data['userData']['appid']

            user_playlist = self.td_qobuz_playlist_getUserPlaylists(parameter='limit=1')
            vit_status = user_playlist.get('vit_status')
            if vit_status!=0:#如果副那会的vit_status不是0的话表示登陆已过期.
                print (json.dumps({"vit_status":1,"vit_message":"103"}))
                return self.td_qobuz_relogin()
            else:
                user_name=user_playlist.get('user',{}).get('login')
                return json.dumps({"vit_status":0,"vit_message":"",'user':user_name})
                # end_time = data['userData']['user']['subscription']['end_date']
                # return json.dumps({"vit_status": 1, "vit_message": str(end_time)})
                # duration = self.td_qobuz_track_getFileUrl(intent="stream", parameter='track_id=117631031&format_id=27').get('duration','0')
                # print(duration)
                # if int(duration)>30:
                #     return json.dumps({"vit_status": 0, 'vit_message': ''})
                # else:
                #     return json.dumps({"vit_status": 0, 'vit_message': '1'})#获取的播放链接只能播放30s，订阅过期了


        else:  # 用户未登陆的情况
            return json.dumps({"vit_status":1,"vit_message":"101"})


    def td_qobuz_relogin(self):
        if os.path.exists(info_path):
            try:
                with open(info_path)as f:
                    data=json.load(f)
            except:
                os.remove(info_path)
                return json.dumps({'vit_status':4,'vit_mesage':'446'})
            username=data.get('username','')
            if not username:
                return json.dumps({'vit_status':2,'vit_mesage':'201'})

            password=data.get('password','')
            if not password:
                return json.dumps({'vit_status':2,'vit_mesage':'202'})
            parameter=f'username={username}&password={password}'

            return self.td_qobuz_user_login(parameter)

    def td_qobuz_index(self, parameter):
        # 获取首页信息
        # 流派，genre_ids: 分类，All genres: 传入该参数，单个 genre 传入值如 10，多个 genres 传入值如 10,80,112
        ka = self.td_qobuz_parameter_dic(parameter)
        status=self.td_qobuz_check_ka(ka, [], ['genre_ids'])
        if status=='pass':
            return self.td_qobuz_api_request(ka, '/featured/index')
        else:
            return status
    def td_qobuz_featured_albums(self, parameter):
        # 获取推荐专辑
        # genre_ids: 分类，All genres: 传入该参数，单个 genre 传入值如 10，多个 genres 传入值如 10,80,112
        ka = self.td_qobuz_parameter_dic(parameter)
        status=self.td_qobuz_check_ka(ka, [], ['genre_ids'])
        if status=='pass':
            return self.td_qobuz_api_request(ka, '/featured/albums')
        else:
            return status

    def td_qobuz_album_getFeatured(self, parameter):
        # 按推荐分类，获取推荐专辑
        # 推荐分类，type: qobuzissims, ideal-discography
        # 流派，genre_ids: 分类，All genres: 传入该参数，单个 genre 传入值如 10，多个 genres 传入值如 10,80,112
        ka = self.td_qobuz_parameter_dic(parameter)
        if 'limit' not in ka:
            ka['limit']=30
        if 'offset' not in ka:
            ka['offset']=0
        status=self.td_qobuz_check_ka(ka, ['type'], ['genre_ids', 'limit', 'offset'])
        if status=='pass':
            return self.td_qobuz_api_request(ka, '/album/getFeatured')
        else:
            return status
    def td_qobuz_playlist_getFeatured(self, parameter):
        # 获取推荐播放列表
        # type: 'editor-picks'
        # 流派, genre_ids: 分类，All genres: 传入该参数，单个 genre 传入值如 10，多个 genres 传入值如 10,80,112
        # 标签, tags: new
        ka = self.td_qobuz_parameter_dic(parameter)
        if 'limit' not in ka:
            ka['limit']=30
        if 'offset' not in ka:
            ka['offset']=0
        status=self.td_qobuz_check_ka(ka, ['type'], ['genre_ids', 'limit', 'offset', 'tags'])
        if status=='pass':
            return self.td_qobuz_api_request(ka, '/playlist/getFeatured')
        else:
            return status
# https://www.qobuz.com/api.json/0.2/playlist/getFeatured?type=editor-picks&offset=0&limit=24&genre_ids=112,80,10,64

    def td_qobuz_parameter_dic(self,parameter):
        parameter_dic = {}
        try:
            parameter_list = parameter.split('&')

            for parameter in parameter_list:
                key = urllib.parse.unquote(parameter.split('=', 1)[0].strip())
                value = urllib.parse.unquote(parameter.split('=', 1)[1].strip())
                parameter_dic[key] = value
            return parameter_dic
        except:
            return parameter_dic

    def td_qobuz_user_login(self,parameter,flag=False):
        try:
            ka= self.td_qobuz_parameter_dic(parameter)
            status=self.td_qobuz_check_ka(ka, ['username', 'password'], ['email'])#参数验证通过会返回True,否则返回相应的状态信息
            if status=='pass': #如果参数验证通过则发送请求，请求后的数据
                password_aes=ka['password']
                ka['password']="".join(os.popen('thunder_aes_cbc128 {}'.format(ka['password'])).readlines()).strip()

                self.spoofer = spoofbuz.Spoofer(flag=flag)
                self.appid = self.spoofer.getAppId()


                data = self.td_qobuz_api_request(ka, '/user/login', noToken=True)

                # if not data or not 'user' in data or not 'credential' in data['user'] \
                #         or not 'id' in data['user'] \
                #         or not 'parameters' in data['user']['credential']:
                #     # warn("/user/login returns %s" % data)
                #     self.logout()
                #     return json.du
                vit_status=data['vit_status']
                vit_message=data['vit_message']
                if vit_status==0:
                    if not data["user"]["credential"]["parameters"]:
                        # data['user']['email'] = ''
                        # data['user']['firstname'] = ''
                        # data['user']['lastname'] = ''
                        self.setSec()
                        data['s4'] = self.s4.decode()
                        data['appid'] = self.appid
                        self.user_id = data['user']['id']
                        self.user_auth_token = data["user_auth_token"]
                        self.label = ''
                        self.td_qobuz_userinfo_save(username=ka['username'],password_aes=password_aes,userData=data)
                        return json.dumps({'vit_status':0,'vit_message':''})#未订阅用户
                    else:

                        self.user_id = data['user']['id']
                        self.user_auth_token = data["user_auth_token"]
                        self.label = data["user"]["credential"]["parameters"]["short_label"]
                        data['user']['email'] = ''
                        data['user']['firstname'] = ''
                        data['user']['lastname'] = ''
                        self.setSec()
                        data['s4'] = self.s4.decode()
                        data['appid']=self.appid
                        self.td_qobuz_userinfo_save(username=ka['username'],password_aes=password_aes,userData=data)
                        return json.dumps({'vit_status':0,'vit_message':''})
                elif vit_status==4 and int(vit_message)==400:
                    self.td_qobuz_user_login(parameter, flag=True)
                else:
                    return json.dumps(data)
            else:#参数验证不通过则返回相应的状态
                return status
        except:
            self.td_qobuz_user_login(parameter,flag=True)

    #存储用户信息。
    def td_qobuz_userinfo_save(self,username, password_aes, userData):
        info_dir = os.path.dirname(info_path)
        if not os.path.exists(info_dir):
            os.makedirs(info_dir)
        with open(info_path, 'w+', encoding='utf8')as f:
            data_save = {'username': username, 'password': password_aes, 'userData': userData}
            f.write(json.dumps(data_save))



def main():
    try:
        td_qobuz_paramter = sys.argv[2]
    except:
        td_qobuz_paramter = ''

    try:
        td_qobuz_manage = sys.argv[1]
    except:
        td_qobuz_manage = ''
    api = RawApi("950096963", "")

# --------------------------------------------------login. USER HANDLING------------------------------------------------
    if td_qobuz_manage == 'user_login':
        print(api.td_qobuz_user_login(parameter=td_qobuz_paramter))
    elif td_qobuz_manage == 'user_re_login':
        print(api.td_qobuz_relogin())
    elif td_qobuz_manage == 'user_logout':
        print(api.td_qobuz_Logout())
    elif td_qobuz_manage == "maybe_login":
        print(api.td_qobuz_maybe_login())

# --------------------------------------------------首页相关-------------------------------------------------------------
    # 首页
    elif td_qobuz_manage == 'index':

        data = api.td_qobuz_maybe_login()
        data = json.loads(data)
        if data["vit_status"] == 0 and data['vit_message'] == '':
            print(json.dumps(api.td_qobuz_index(parameter=td_qobuz_paramter)))
        else:
            print(json.dumps(data))
#--------------------------------------------------获取所有的流派---------------------------------------------------------
    # ALL genres
    elif td_qobuz_manage == 'all_genres':
        data = api.td_qobuz_maybe_login()
        data = json.loads(data)
        if data["vit_status"] == 0 and data['vit_message'] == '':
            print(json.dumps(api.td_qobuz_genre_list(parameter=td_qobuz_paramter)))
        else:
            print(json.dumps(data))
# --------------------------------------------------专辑相关--------------------------------------------------------------
    # 获取推荐专辑
    elif td_qobuz_manage == 'featured_albums':
        data = api.td_qobuz_maybe_login()
        data = json.loads(data)
        if data["vit_status"] == 0 and data['vit_message'] == '':
            print(json.dumps(api.td_qobuz_featured_albums(parameter=td_qobuz_paramter)))
        else:
            print(json.dumps(data))
    # 获取不同类类型的推荐专辑
    elif td_qobuz_manage == 'album_getfeatured':
        data = api.td_qobuz_maybe_login()
        data = json.loads(data)
        if data["vit_status"] == 0 and data['vit_message'] == '':
            print(json.dumps(api.td_qobuz_album_getFeatured(parameter=td_qobuz_paramter)))
        else:
            print(json.dumps(data))
    # 获取专辑的详细信息。
    elif td_qobuz_manage == 'album_detail':
        data = api.td_qobuz_maybe_login()
        data = json.loads(data)
        if data["vit_status"] == 0 and data['vit_message'] == '':
            print(json.dumps(api.td_qobuz_album_get(parameter=td_qobuz_paramter)))
        else:
            print(json.dumps(data))
    # 获取歌曲的播放地址
    elif td_qobuz_manage == 'get_file_url':
        data = api.td_qobuz_maybe_login()
        data = json.loads(data)
        if data["vit_status"] == 0 and data['vit_message'] == '':

            print(json.dumps(api.td_qobuz_track_getFileUrl(parameter=td_qobuz_paramter)))
        else:
            print(json.dumps(data))

    elif td_qobuz_manage == 'artist_detail':
        data = api.td_qobuz_maybe_login()
        data = json.loads(data)
        if data['vit_status'] == 0 and data['vit_message'] == '':
            print(json.dumps(api.td_qobuz_artist_get(parameter=td_qobuz_paramter)))
        else:
            print(json.dumps(data))
# ----------------------------------------------播放列表相关--------------------------------------------------------------
    # Qobuz playlists
    elif td_qobuz_manage == 'qobuz_playlists':
        data = api.td_qobuz_maybe_login()
        data = json.loads(data)
        if data["vit_status"] == 0 and data['vit_message'] == '':
            print(json.dumps(api.td_qobuz_playlist_getFeatured(parameter=td_qobuz_paramter)))
        else:
            print(json.dumps(data))
    # 获取播放列表分类的tags的值
    elif td_qobuz_manage == 'playlist_tags':
        data = api.td_qobuz_maybe_login()
        data = json.loads(data)
        if data["vit_status"] == 0 and data['vit_message'] == '':
            print(json.dumps(api.td_qobuz_featured_playlist_tags(parameter=td_qobuz_paramter)))
        else:
            print(json.dumps(data))
    # 获取播放列表详细
    elif td_qobuz_manage == 'playlist_detail':
        data = api.td_qobuz_maybe_login()
        data = json.loads(data)
        if data["vit_status"] == 0 and data['vit_message'] == '':

            print(json.dumps(api.td_qobuz_playlist_get(parameter=td_qobuz_paramter)))
        else:
            print(json.dumps(data))
    elif td_qobuz_manage=='playlist_subscribe':
        data = api.td_qobuz_maybe_login()
        data = json.loads(data)
        if data["vit_status"] == 0 and data['vit_message'] == '':

            print(json.dumps(api.td_qobuz_playlist_subscribe(parameter=td_qobuz_paramter)))
        else:
            print(json.dumps(data))
    elif td_qobuz_manage == 'playlist_unsubscribe':
        data = api.td_qobuz_maybe_login()
        data = json.loads(data)
        if data["vit_status"] == 0 and data['vit_message'] == '':

            print(json.dumps(api.td_qobuz_playlist_unsubscribe(parameter=td_qobuz_paramter)))
        else:
            print(json.dumps(data))
# ----------------------------------------------Myplaylist相关-----------------------------------------------------------
    elif td_qobuz_manage == 'get_user_playlists':
        data = api.td_qobuz_maybe_login()
        data = json.loads(data)
        if data["vit_status"] == 0 and data['vit_message'] == '':
            print(json.dumps(api.td_qobuz_playlist_getUserPlaylists(parameter=td_qobuz_paramter)))
        else:
            print(json.dumps(data))
    elif td_qobuz_manage == 'user_playlist_create':
        data = api.td_qobuz_maybe_login()
        data = json.loads(data)
        if data["vit_status"] == 0 and data['vit_message'] == '':
            print(json.dumps(api.td_qobuz_playlist_create(parameter=td_qobuz_paramter)))
        else:
            print(json.dumps(data))
    elif td_qobuz_manage == 'user_playlist_delete':
        data = api.td_qobuz_maybe_login()
        data = json.loads(data)
        if data["vit_status"] == 0 and data['vit_message'] == '':
            print(json.dumps(api.td_qobuz_playlist_delete(parameter=td_qobuz_paramter)))
        else:
            print(json.dumps(data))

    elif td_qobuz_manage == 'user_playlist_update':
        data = api.td_qobuz_maybe_login()
        data = json.loads(data)
        if data["vit_status"] == 0 and data['vit_message'] == '':
            print(json.dumps(api.td_qobuz_playlist_update(parameter=td_qobuz_paramter)))
        else:
            print(json.dumps(data))
    elif td_qobuz_manage == 'playlist_addtracks':
        data = api.td_qobuz_maybe_login()
        data = json.loads(data)
        if data["vit_status"] == 0 and data['vit_message'] == '':
            print(json.dumps(api.td_qobuz_playlist_addTracks(parameter=td_qobuz_paramter)))
        else:
            print(json.dumps(data))
    elif td_qobuz_manage == 'playlist_deletetracks':
        data = api.td_qobuz_maybe_login()
        data = json.loads(data)

        if data["vit_status"] == 0 and data['vit_message'] == '':
            print(json.dumps(api.td_qobuz_playlist_deleteTracks(parameter=td_qobuz_paramter)))
        else:
            print(json.dumps(data))
# --------------------------------------------收藏相关-------------------------------------------------------------------
    elif td_qobuz_manage =='favorite_ids':
        data = api.td_qobuz_maybe_login()
        data = json.loads(data)

        if data["vit_status"] == 0 and data['vit_message'] == '':
            print(json.dumps(api.td_qobuz_user_favorite_ids(parameter=td_qobuz_paramter)))
        else:
            print(json.dumps(data))
    elif td_qobuz_manage == 'favorite_create':
        # 收藏添加:传入 'artist_ids', 'album_ids', 'track_ids',可在收藏中添加歌手 专辑、歌曲。多个id用','隔开
        data = api.td_qobuz_maybe_login()
        data = json.loads(data)

        if data["vit_status"] == 0 and data['vit_message'] == '':
            print(json.dumps(api.td_qobuz_favorite_create(parameter=td_qobuz_paramter)))
        else:
            print(json.dumps(data))
    elif td_qobuz_manage == 'favorite_delete':
        # 收藏移除：传入 'artist_ids', 'album_ids', 'track_ids',可删除收藏的歌手 专辑、歌曲。多个id用','隔开
        data = api.td_qobuz_maybe_login()
        data = json.loads(data)
        if data["vit_status"] == 0 and data['vit_message'] == '':
            print(json.dumps(api.td_qobuz_favorite_delete(parameter=td_qobuz_paramter)))
        else:
            print(json.dumps(data))
    elif td_qobuz_manage == 'get_User_Favorites':
        # 获取我的收藏
        data = api.td_qobuz_maybe_login()
        data = json.loads(data)
        if data["vit_status"] == 0 and data['vit_message'] == '':
            print(json.dumps(api.td_qobuz_favorite_getUserFavorites(parameter=td_qobuz_paramter)))
        else:
            print(json.dumps(data))
# ---------------------------------------------搜索相关功能---------------------------------------------------------------
    elif td_qobuz_manage == 'catalog_search':
        data = api.td_qobuz_maybe_login()
        data = json.loads(data)
        if data["vit_status"] == 0 and data['vit_message'] == '':
            print(json.dumps(api.td_qobuz_catalog_search(parameter=td_qobuz_paramter)))
        else:
            print(json.dumps(data))
    elif td_qobuz_manage == 'track_search':
        data = api.td_qobuz_maybe_login()
        data = json.loads(data)
        if data["vit_status"] == 0 and data['vit_message'] == '':
            print(json.dumps(api.td_qobuz_track_search(parameter=td_qobuz_paramter)))
        else:
            print(json.dumps(data))
    elif td_qobuz_manage == 'album_search':
        data = api.td_qobuz_maybe_login()
        data = json.loads(data)
        if data["vit_status"] == 0 and data['vit_message'] == '':
            print(json.dumps(api.td_qobuz_album_search(parameter=td_qobuz_paramter)))
        else:
            print(json.dumps(data))
    elif td_qobuz_manage == 'artist_search':
        data = api.td_qobuz_maybe_login()
        data = json.loads(data)
        if data["vit_status"] == 0 and data['vit_message'] == '':
            print(json.dumps(api.td_qobuz_artist_search(parameter=td_qobuz_paramter)))
        else:
            print(json.dumps(data))
    elif td_qobuz_manage == 'playlist_search':
        data = api.td_qobuz_maybe_login()
        data = json.loads(data)
        if data["vit_status"] == 0 and data['vit_message'] == '':
            print(json.dumps(api.td_qobuz_playlist_search(parameter=td_qobuz_paramter)))
        else:
            print(json.dumps(data))

# -------------------------------------------------其他功能--------------------------------------------------------------
            # 获取精选分类
            # 返回分类列表，如 best-seller, new-releases, press-awards, most-streamed, editor-picks, most-featured
    elif td_qobuz_manage == 'get_featured_types':
        data = api.td_qobuz_maybe_login()
        data = json.loads(data)
        if data["vit_status"] == 0 and data['vit_message'] == '':
            print(json.dumps(api.td_qobuz_catalog_getFeaturedTypes(parameter=td_qobuz_paramter)))
        else:
            print(json.dumps(data))
    # 获取精选目录
    # 返回 艺术家、专辑、播放列表、文章
    elif td_qobuz_manage == 'get_featured':
        data = api.td_qobuz_maybe_login()
        data = json.loads(data)
        if data["vit_status"] == 0 and data['vit_message'] == '':
            print(json.dumps(api.td_qobuz_catalog_getFeatured(parameter=td_qobuz_paramter)))
        else:
            print(json.dumps(data))
    else:
        # 98:987是没有输入正确的功能
        print(json.dumps({"vit_status": 98, "vit_message": "987"}))
        # sys.exit(98)


if __name__ == '__main__':
    main()
