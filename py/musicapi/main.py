import config
import uvicorn
from fastapi import FastAPI, Request, Depends
from starlette.responses import JSONResponse


app = FastAPI(**config.FastapiInfo, docs_url=None, redoc_url=None)
from mainfun import *
from tidal import tidal
from amazon import amazon
from qobuz import qobuz
from fastapi.openapi.docs import (get_redoc_html, get_swagger_ui_html, get_swagger_ui_oauth2_redirect_html, )
from fastapi.staticfiles import StaticFiles

logger.remove(handler_id=None)  # 清除之前的设置,不输出到console
# 日志设置
path_log_error = os.path.join(pathLogger, 'error.log')
path_log_info = os.path.join(pathLogger, 'info.log')
# 路径，每日分割时间，是否异步记录，日志是否序列化，编码格式，最长保存日志时间
Format = '{time:YYYY-MM-DD HH:mm:ss} - {level} - {file} - {line} - {message}'
logger.add(path_log_info, rotation='50 MB', format=Format, enqueue=True, serialize=False, encoding="utf-8", retention="3 days", level="INFO",
           compression="zip")  # ,backtrace=True,diagnose=True
logger.debug("服务器重启！")

async def logging_dependency(request: Request):
    logger.info(f" {request.method} {request.url}   {request.client.host}")

# @app.middleware("http")  # 中间件，获取返回状态保存到日志中
# def add_process_time_header(request: Request, call_next):  # 该拦截器和后台任务出现阻塞
#     response = call_next(request)
#     try:
#         logger.info(f"--{response.status_code}-- {request.method} {request.url}   {request.client.host}")#
#     except:
#         pass
#     return response


@app.exception_handler(Exception)  # 异常处理，保存错误日志
async def exception_callback(request: Request, exc: Exception):
    logger.error(f"--500-- {request.method} {request.url}")
    logger.exception(exc)
    return JSONResponse({'vit_status': 5, 'vit_message': 'Internal Server Error'}, status_code=500)  # Internal Server Error


# ############################### tidal ###########################################################
app.include_router(tidal.router, dependencies=[Depends(logging_dependency)])  # 添加tidal路由

tidalhomepage_thread = threading.Thread(target=getTidalHomepage)  # tidal页面缓存线程： 获取tidal每个页面
tidalhomepage_thread.daemon = True
tidalhomepage_thread.start()

tidal_cache_thread = threading.Thread(target=cacheTidalQueue)  # tidal缓存队列线程
tidal_cache_thread.daemon = True
tidal_cache_thread.start()

# ############################### amazon ###########################################################
app.include_router(amazon.router, dependencies=[Depends(logging_dependency)])  # 添加amazon路由

amazonhomepage_thread = threading.Thread(target=getAmazonHomepage)  # amazon页面缓存线程
amazonhomepage_thread.daemon = True
amazonhomepage_thread.start()

amazon_cache_thread = threading.Thread(target=cacheAmazonQueue)  # amazon缓存队列线程
amazon_cache_thread.daemon = True
amazon_cache_thread.start()

# ############################### qobuz ###########################################################
app.include_router(qobuz.router, dependencies=[Depends(logging_dependency)])  # 添加qobuz路由

app.mount('/python/static', StaticFiles(directory=os.path.join(staticDir, 'static')), name='static')


@app.get("/python/docs", include_in_schema=False)  # 接口文档docs
def custom_swagger_ui_html():
    if config.debug == True:
        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=app.title + " - Swagger UI",
            oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
            swagger_js_url="/python/static/swagger-ui/swagger-ui-bundle.js",
            swagger_css_url="/python/static/swagger-ui/swagger-ui.css",
        )
    else:
        return {"detail": "Not Found"}


@app.get(app.swagger_ui_oauth2_redirect_url, include_in_schema=False)
def swagger_ui_redirect():
    return get_swagger_ui_oauth2_redirect_html()


@app.get("/python/redoc", include_in_schema=False)  # 接口文档docs
def redoc_html():
    if config.debug == True:
        return get_redoc_html(
            openapi_url=app.openapi_url,
            title=app.title + " - ReDoc",
            redoc_js_url="/python/static/swagger-ui/redoc.standalone.js",
        )
    else:
        return {"detail": "Not Found"}


if __name__ == '__main__':
    uvicorn.run(app, host=serverIP, port=6599, debug=True)
