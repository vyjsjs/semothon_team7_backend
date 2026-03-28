from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

# .env 파일의 환경 변수 불러오기
load_dotenv()

app = FastAPI()

# 프론트엔드 연동을 위한 CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# DB 연동 전 프론트엔드 테스트를 위한 임시 메모리 데이터
mock_users = []

@app.get("/")
def read_root():
    return {"message": "서버가 정상 작동 중입니다. (DB 미연동 상태)"}

@app.post("/users")
def create_user_mock(nickname: str, target_sleep_time: str):
    fake_user = {
        "id": "temp-uuid-1234", 
        "nickname": nickname, 
        "target_sleep_time": target_sleep_time
    }
    mock_users.append(fake_user)
    return {"status": "success", "data": fake_user}