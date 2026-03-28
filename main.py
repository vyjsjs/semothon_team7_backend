from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client
import os
from dotenv import load_dotenv
import uuid
from typing import List
from datetime import datetime, timezone
from typing import Optional

# 환경변수 로드
load_dotenv()

app = FastAPI()

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Supabase 클라이언트 초기화
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# --- Pydantic 모델 정의 (요청 데이터 검증용) ---

class LoginRequest(BaseModel):
    username: str
    password: str

class NicknameRequest(BaseModel):
    nickname: str

class GroupRequest(BaseModel):
    group_name: str

class UserInfoUpdateRequest(BaseModel):
    nickname: str
    target_sleep_time: str

class GroupChangeRequest(BaseModel):
    group_id: str

# --- API 엔드포인트 구현 ---

@app.get("/")
def read_root():
    return {"message": "수면 서비스 백엔드 서버가 정상 작동 중입니다."}

# 1. 인증: 로그인
@app.post("/api/auth/login")
def login(request: LoginRequest):
    # 실제 환경에서는 Supabase Auth(supabase.auth.sign_in_with_password)를 사용하거나
    # users 테이블에서 비밀번호 해시를 검증해야 합니다.
    # 여기서는 명세서의 응답 형태에 맞춘 예시 코드를 작성합니다.
    try:
        # 예시: 임의의 토큰과 유저 ID 반환 (실제 연동 시 수정 필요)
        mock_access_token = "mock_header.mock_payload.mock_signature"
        mock_user_id = str(uuid.uuid4())
        
        return {
            "status": "success",
            "data": {
                "access_token": mock_access_token,
                "user_id": mock_user_id
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# 2. 온보딩: 닉네임 설정
@app.put("/api/users/nickname")
def set_nickname(request: NicknameRequest):
    # 실제 환경에서는 Header의 토큰을 검증하여 user_id를 추출한 뒤 데이터를 업데이트해야 합니다.
    try:
        # DB 업데이트 로직 예시 (주석 처리)
        # supabase.table("users").update({"nickname": request.nickname}).eq("id", current_user_id).execute()
        
        return {
            "status": "success",
            "message": "닉네임이 설정되었습니다."
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# 3. 온보딩: 그룹 생성
@app.post("/api/groups")
def create_group(request: GroupRequest):
    try:
        # DB 인서트 로직 예시 (주석 처리)
        # response = supabase.table("groups").insert({"name": request.group_name}).execute()
        
        # 임의의 응답 데이터 생성
        new_group_id = str(uuid.uuid4())
        invite_code = "SLEEP123" # 난수 생성 로직으로 대체 필요
        
        return {
            "status": "success",
            "data": {
                "group_id": new_group_id,
                "invite_code": invite_code
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- 추가 Pydantic 모델 정의 ---

class TargetTimeRequest(BaseModel):
    target_sleep_time: str

class SleepStartRequest(BaseModel):
    goodnight_message: str

class SleepStopRequest(BaseModel):
    session_id: str


# 4. 온보딩/설정: 목표 시간 설정
@app.put("/api/users/target-time")
def set_target_time(request: TargetTimeRequest):
    try:
        # DB 업데이트 로직 (주석 처리)
        # supabase.table("users").update({"target_sleep_time": request.target_sleep_time}).eq("id", current_user_id).execute()
        
        return {
            "status": "success",
            "message": "목표 시간이 설정되었습니다."
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# 5. 홈: 메인 데이터 조회
@app.get("/api/home")
def get_home_data():
    # 실제 환경에서는 Header의 Authorization 토큰을 검증하여 사용자 정보를 가져옵니다.
    try:
        # DB 조회 로직 예시 (주석 처리)
        # user_data = supabase.table("users").select("nickname, target_sleep_time, current_status").eq("id", current_user_id).single().execute()
        
        return {
            "status": "success",
            "data": {
                "nickname": "사용자닉네임",
                "target_time": "23:30",
                "current_status": "awake" # awake 또는 sleeping
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# 6. 홈: 수면 피드 조회
@app.get("/api/feed")
def get_sleep_feed():
    try:
        # 같은 그룹에 속한 사용자들의 현재 상태를 조회하는 DB 로직 (주석 처리)
        # feed_data = supabase.table("users").select("id, nickname, current_status").eq("group_id", user_group_id).execute()
        
        return {
            "status": "success",
            "data": [
                {
                    "user_id": str(uuid.uuid4()),
                    "nickname": "팀원1",
                    "status": "sleeping"
                },
                {
                    "user_id": str(uuid.uuid4()),
                    "nickname": "팀원2",
                    "status": "awake"
                }
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# 7. 수면: 찌르기
@app.post("/api/users/{user_id}/poke")
def poke_user(user_id: str):
    # 대상 user_id를 경로 매개변수(Path Parameter)로 받습니다.
    try:
        # 알림 테이블(notifications)에 찌르기 이벤트를 추가하는 DB 로직 (주석 처리)
        # supabase.table("notifications").insert({"target_user_id": user_id, "type": "poke"}).execute()
        
        return {
            "status": "success",
            "message": "찌르기 알림을 전송했습니다."
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# 8. 수면: 수면 시작
@app.post("/api/sleep/start")
def start_sleep(request: SleepStartRequest):
    try:
        # DB에 수면 세션 시작 기록 생성 (주석 처리)
        # current_time = datetime.now(timezone.utc).isoformat()
        # insert_data = {"user_id": current_user_id, "start_time": current_time, "goodnight_message": request.goodnight_message}
        # response = supabase.table("sleep_records").insert(insert_data).execute()
        
        session_id = str(uuid.uuid4())
        start_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        return {
            "status": "success",
            "data": {
                "session_id": session_id,
                "start_time": start_time
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# 9. 수면: 수면 종료
@app.post("/api/sleep/stop")
def stop_sleep(request: SleepStopRequest):
    try:
        # DB에서 해당 세션 ID의 수면 기록 종료 시간 업데이트 및 총 수면 시간 계산 (주석 처리)
        # end_time = datetime.now(timezone.utc).isoformat()
        # supabase.table("sleep_records").update({"end_time": end_time}).eq("id", request.session_id).execute()
        
        end_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        total_sleep_minutes = 450 # 임의의 계산된 수면 시간(분)
        
        return {
            "status": "success",
            "data": {
                "end_time": end_time,
                "total_sleep_minutes": total_sleep_minutes
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# 10. 설정: 내 정보 조회
@app.get("/api/users/me")
def get_my_info():
    try:
        # Header의 토큰으로 사용자 정보를 DB에서 조회 (주석 처리)
        # user_data = supabase.table("users").select("nickname, target_sleep_time, group_id").eq("id", current_user_id).single().execute()
        
        return {
            "status": "success",
            "data": {
                "nickname": "사용자닉네임",
                "target_time": "23:30",
                "group_id": str(uuid.uuid4())
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# 11. 설정: 내 정보 수정
@app.put("/api/users/me")
def update_my_info(request: UserInfoUpdateRequest):
    try:
        # DB의 사용자 정보 업데이트 (주석 처리)
        # update_data = {"nickname": request.nickname, "target_sleep_time": request.target_sleep_time}
        # supabase.table("users").update(update_data).eq("id", current_user_id).execute()
        
        return {
            "status": "success",
            "message": "정보가 수정되었습니다."
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# 12. 설정: 그룹 변경
@app.put("/api/users/group")
def change_group(request: GroupChangeRequest):
    try:
        # DB의 사용자 그룹 ID 업데이트 (주석 처리)
        # supabase.table("users").update({"group_id": request.group_id}).eq("id", current_user_id).execute()
        
        return {
            "status": "success",
            "message": "그룹이 변경되었습니다."
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# 13. 메뉴: 알림 조회
@app.get("/api/notifications")
def get_notifications(page: int = 1):
    # Query Parameter로 page를 받습니다.
    try:
        # DB에서 알림 내역을 페이지네이션하여 조회 (주석 처리)
        # offset = (page - 1) * 10
        # noti_data = supabase.table("notifications").select("*").eq("target_user_id", current_user_id).range(offset, offset + 9).execute()
        
        return {
            "status": "success",
            "data": [
                {
                    "id": str(uuid.uuid4()),
                    "type": "poke",
                    "message": "팀원1님이 회원님을 찔렀습니다.",
                    "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                }
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# 14. 메뉴: 리포트 조회
@app.get("/api/reports")
def get_reports(period: str = "weekly"):
    # Query Parameter로 period를 받습니다.
    try:
        # DB에서 기간 내 수면 기록을 바탕으로 통계 산출 (주석 처리)
        # 리포트 계산 로직 필요
        
        return {
            "status": "success",
            "data": {
                "avg_sleep_minutes": 420,
                "achievement_rate": 85
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))