from flask import Flask
from flask_cors import CORS
from flask_restx import Api
import logging
from logging.handlers import RotatingFileHandler
from english import English
from japanese import Japanese


app = Flask(__name__)
CORS(app, supports_credentials=True)

api = Api(
    app,
    version='0.1',
    title="Metaverse English!",
    description="메타버스로 영어공부하기",
    terms_url="/",
    contact="jungmo324@naver.com",
    license=""
)

# Flask-RESTx의 기본 에러 처리를 비활성화합니다.
app.config["ERROR_404_HELP"] = False
app.config["BUNDLE_ERRORS"] = True

@api.errorhandler(Exception)  # 모든 예외 유형에 대한 에러 핸들러를 정의합니다.
def handle_error(error):
    return {"message": "An error occurred while processing the request."}

log_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] - %(message)s"
)  # 로그 메시지의 형식을 정의합니다.

log_handler = RotatingFileHandler(
    "flask_app.log", maxBytes=10000000, backupCount=1
)  # 로그 파일 핸들러를 생성하고 파일 이름과 크기 제한, 백업 파일 수를 설정합니다.
log_handler.setFormatter(log_formatter)  # 로그 파일 핸들러에 형식을 설정합니다.

# 로깅 레벨에 따라 로그를 기록하도록 설정합니다. 이 예에서는 DEBUG 레벨 이상의 로그만 기록합니다.
app.logger.setLevel(logging.INFO)  
app.logger.addHandler(log_handler) 

api.add_namespace(Japanese, '/japanese')
api.add_namespace(English, '/english')
