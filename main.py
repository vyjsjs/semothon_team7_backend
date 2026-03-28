from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client
import os
from dotenv import load_dotenv
import uuid
import random
import string
from typing import List, Optional
from datetime import datetime, timezone

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

# --- 의존성 주입: 현재 유저 식별 ---
def get_current_user_id(authorization: str = Header(None)):
    # 해커톤 테스트를 위한 임시 식별 로직입니다. 
    # 실제로는 토큰을 해독하여 users 테이블의 int8 형태 id를 반환해야 합니다.
    if authorization and authorization.isdigit():
        return int(authorization)
    return 1  # 기본값

# --- Pydantic 모델 정의 (요청 데이터 검증용) ---

class LoginRequest(BaseModel):
    username: str
    password: str

class NicknameRequest(BaseModel):
    nickname: str

class GroupRequest(BaseModel):
    group_name: str

class GroupJoinRequest(BaseModel):
    invite_code: str

class TargetTimeRequest(BaseModel):
    target_sleep_time: str

class SleepStartRequest(BaseModel):
    goodnight_message: str

class SleepStopRequest(BaseModel):
    session_id: str

class UserInfoUpdateRequest(BaseModel):
    nickname: str
    target_sleep_time: str

class GroupChangeRequest(BaseModel):
    group_id: int

# --- API 엔드포인트 구현 ---

@app.get("/")
def read_root():
    return {"message": "수면 서비스 백엔드 서버가 정상 작동 중입니다."}

# 1. 인증: 로그인
@app.post("/api/auth/login")
def login(request: LoginRequest):
    try:
        mock_access_token = "mock_token_123"
        return {
            "status": "success",
            "data": {
                "access_token": mock_access_token,
                "user_id": "1" # 스키마의 int8 id에 대응
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# 2. 온보딩: 닉네임 설정
@app.put("/api/users/nickname")
def set_nickname(request: NicknameRequest, user_id: int = Depends(get_current_user_id)):
    try:
        supabase.table("users").update({"nickname": request.nickname}).eq("id", user_id).execute()
        return {
            "status": "success",
            "message": "닉네임이 설정되었습니다."
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# 3. 온보딩: 그룹 생성
@app.post("/api/groups")
def create_group(request: GroupRequest, user_id: int = Depends(get_current_user_id)):
    try:
        invite_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        group_res = supabase.table("groups").insert({"name": request.group_name, "invite_code": invite_code}).execute()
        group_id = group_res.data[0]['id']
        
        supabase.table("group_member").insert({"group_id": group_id, "user_id": user_id}).execute()
        
        return {
            "status": "success",
            "data": {
                "group_id": group_id,
                "invite_code": invite_code
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# 3-1. 온보딩: 그룹 가입
@app.post("/api/groups/join")
def join_group(request: GroupJoinRequest, user_id: int = Depends(get_current_user_id)):
    try:
        group_res = supabase.table("groups").select("id, name").eq("invite_code", request.invite_code).execute()
        if not group_res.data:
            raise ValueError("유효하지 않은 초대 코드입니다.")
            
        group_id = group_res.data[0]['id']
        supabase.table("group_member").insert({"group_id": group_id, "user_id": user_id}).execute()
        
        return {
            "status": "success",
            "data": {
                "group_id": group_id,
                "group_name": group_res.data[0]['name']
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# 4. 온보딩/설정: 목표 시간 설정
@app.put("/api/users/target-time")
def set_target_time(request: TargetTimeRequest, user_id: int = Depends(get_current_user_id)):
    try:
        supabase.table("users").update({"target_time": request.target_sleep_time}).eq("id", user_id).execute()
        return {
            "status": "success",
            "message": "목표 시간이 설정되었습니다."
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# 5. 홈: 메인 데이터 조회
@app.get("/api/home")
def get_home_data(user_id: int = Depends(get_current_user_id)):
    try:
        user_res = supabase.table("users").select("nickname, target_time, current_status").eq("id", user_id).single().execute()
        return {
            "status": "success",
            "data": {
                "nickname": user_res.data.get("nickname"),
                "target_time": user_res.data.get("target_time"),
                "current_status": user_res.data.get("current_status", "awake")
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# 6. 홈: 수면 피드 조회
@app.get("/api/feed")
def get_sleep_feed(user_id: int = Depends(get_current_user_id)):
    try:
        gm_res = supabase.table("group_member").select("group_id").eq("user_id", user_id).execute()
        if not gm_res.data:
            return {"status": "success", "data": []}
            
        group_id = gm_res.data[0]['group_id']
        members_res = supabase.table("group_member").select("user_id").eq("group_id", group_id).execute()
        member_ids = [m['user_id'] for m in members_res.data]
        
        users_res = supabase.table("users").select("id, nickname, current_status").in_("id", member_ids).execute()
        
        feed_data = []
        for u in users_res.data:
            feed_data.append({
                "user_id": str(u['id']),
                "nickname": u['nickname'],
                "status": u.get('current_status', 'awake')
            })
            
        return {
            "status": "success",
            "data": feed_data
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# 7. 수면: 찌르기
@app.post("/api/users/{target_id}/poke")
def poke_user(target_id: int, user_id: int = Depends(get_current_user_id)):
    try:
        supabase.table("pokes").insert({"sender_id": user_id, "receiver_id": target_id}).execute()
        supabase.table("notifications").insert({
            "user_id": target_id, 
            "type": "poke", 
            "content": "콕 찌르기 알림을 받았습니다.", 
            "is_read": False
        }).execute()
        
        return {
            "status": "success",
            "message": "찌르기 알림을 전송했습니다."
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# 8. 수면: 수면 시작
@app.post("/api/sleep/start")
def start_sleep(request: SleepStartRequest, user_id: int = Depends(get_current_user_id)):
    try:
        current_time = datetime.now(timezone.utc).isoformat()
        record_res = supabase.table("sleep_records").insert({
            "user_id": user_id,
            "status": "sleeping",
            "start_time": current_time
        }).execute()
        
        supabase.table("users").update({"current_status": "sleeping"}).eq("id", user_id).execute()
        
        return {
            "status": "success",
            "data": {
                "session_id": str(record_res.data[0]['id']),
                "start_time": current_time
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# 9. 수면: 수면 종료 (수정본)
@app.post("/api/sleep/stop")
def stop_sleep(request: SleepStopRequest, user_id: int = Depends(get_current_user_id)):
    try:
        current_time_dt = datetime.now(timezone.utc)
        current_time_iso = current_time_dt.isoformat()
        
        # 1. 시작 시간 조회
        record_res = supabase.table("sleep_records").select("start_time").eq("id", request.session_id).single().execute()
        start_time_dt = datetime.fromisoformat(record_res.data['start_time'].replace('Z', '+00:00'))
        
        # 2. 총 수면 시간 계산
        diff = current_time_dt - start_time_dt
        total_minutes = int(diff.total_seconds() // 60)
        
        # 3. 유저의 목표 수면 시간 조회 및 달성 여부 판단
        # users 테이블의 sleep_goal_time(int4, 분 단위)을 기준으로 계산합니다. 값이 없으면 420분(7시간)으로 임의 적용합니다.
        user_res = supabase.table("users").select("sleep_goal_time").eq("id", user_id).single().execute()
        goal_minutes = user_res.data.get('sleep_goal_time')
        if not goal_minutes:
            goal_minutes = 420 
            
        is_achieved = total_minutes >= goal_minutes
        
        # 4. 수면 기록 및 유저 상태 업데이트
        supabase.table("sleep_records").update({
            "end_time": current_time_iso,
            "status": "awake",
            "total_sleep_minutes": total_minutes,
            "is_goal_achieved": is_achieved
        }).eq("id", request.session_id).execute()
        
        supabase.table("users").update({"current_status": "awake"}).eq("id", user_id).execute()
        
        return {
            "status": "success",
            "data": {
                "end_time": current_time_iso,
                "total_sleep_minutes": total_minutes,
                "is_goal_achieved": is_achieved
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# 10. 설정: 내 정보 조회
@app.get("/api/users/me")
def get_my_info(user_id: int = Depends(get_current_user_id)):
    try:
        user_res = supabase.table("users").select("nickname, target_time").eq("id", user_id).single().execute()
        gm_res = supabase.table("group_member").select("group_id").eq("user_id", user_id).execute()
        
        group_id = gm_res.data[0]['group_id'] if gm_res.data else None
        
        return {
            "status": "success",
            "data": {
                "nickname": user_res.data.get("nickname"),
                "target_time": user_res.data.get("target_time"),
                "group_id": group_id
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# 11. 설정: 내 정보 수정
@app.put("/api/users/me")
def update_my_info(request: UserInfoUpdateRequest, user_id: int = Depends(get_current_user_id)):
    try:
        supabase.table("users").update({
            "nickname": request.nickname,
            "target_time": request.target_sleep_time
        }).eq("id", user_id).execute()
        
        return {
            "status": "success",
            "message": "정보가 수정되었습니다."
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# 12. 설정: 그룹 변경
@app.put("/api/users/group")
def change_group(request: GroupChangeRequest, user_id: int = Depends(get_current_user_id)):
    try:
        existing = supabase.table("group_member").select("id").eq("user_id", user_id).execute()
        if existing.data:
            supabase.table("group_member").update({"group_id": request.group_id}).eq("user_id", user_id).execute()
        else:
            supabase.table("group_member").insert({"group_id": request.group_id, "user_id": user_id}).execute()
        
        return {
            "status": "success",
            "message": "그룹이 변경되었습니다."
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# 13. 메뉴: 알림 조회
@app.get("/api/notifications")
def get_notifications(page: int = 1, user_id: int = Depends(get_current_user_id)):
    try:
        offset = (page - 1) * 10
        noti_res = supabase.table("notifications").select("*").eq("user_id", user_id).order("created_at", desc=True).range(offset, offset + 9).execute()
        
        return {
            "status": "success",
            "data": noti_res.data
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# 14. 메뉴: 리포트 조회 (수정본)
@app.get("/api/reports")
def get_reports(period: str = "weekly", user_id: int = Depends(get_current_user_id)):
    try:
        # 해당 유저의 수면 기록 조회 (total_sleep_minutes가 존재하는 완료된 세션 기준)
        records_res = supabase.table("sleep_records").select("total_sleep_minutes, is_goal_achieved").eq("user_id", user_id).execute()
        
        valid_records = [r for r in records_res.data if r.get('total_sleep_minutes') is not None]
        total_count = len(valid_records)
        
        if total_count == 0:
            return {
                "status": "success",
                "data": {
                    "avg_sleep_minutes": 0,
                    "achievement_rate": 0
                }
            }
            
        total_minutes_list = [r['total_sleep_minutes'] for r in valid_records]
        avg_minutes = sum(total_minutes_list) / total_count
        
        achieved_count = sum(1 for r in valid_records if r.get('is_goal_achieved') is True)
        achievement_rate = int((achieved_count / total_count) * 100)
        
        return {
            "status": "success",
            "data": {
                "avg_sleep_minutes": int(avg_minutes),
                "achievement_rate": achievement_rate
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# 15. 수면: 수면 결과 상세 조회
@app.get("/api/sleep/records/{session_id}")
def get_sleep_record(session_id: str, user_id: int = Depends(get_current_user_id)):
    try:
        record_res = supabase.table("sleep_records").select(
            "start_time, end_time, total_sleep_minutes, is_goal_achieved"
        ).eq("id", session_id).single().execute()
        
        if not record_res.data:
            raise ValueError("해당 수면 기록을 찾을 수 없습니다.")
            
        return {
            "status": "success",
            "data": record_res.data
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))