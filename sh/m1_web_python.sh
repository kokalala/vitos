#!/bin/sh

# 开机时运行python服务

if [ -f "/mnt/settings/need_rf_qobuz_cache" ]; then
    if [ -d "/mnt/streaming_cache/qobuz" ]; then
        rm -rf "/mnt/streaming_cache/qobuz"
    fi

    rm -rf "/mnt/settings/need_rf_qobuz_cache"
fi

uvicorn --app-dir /srv/py/musicapi/ main:app --host "0.0.0.0" --port 6599 --reload
