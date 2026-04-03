from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from supabase import create_client, Client
import os
from dotenv import load_dotenv
import uuid
import random
import string
from typing import List, Optional
from datetime import datetime, timezone, timedelta

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

security = HTTPBearer()

# --- 의존성 주입: 실제 JWT 토큰 검증 및 UUID 반환 ---
def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        user_response = supabase.auth.get_user(token)
        if not user_response or not user_response.user:
            raise ValueError("유효하지 않은 토큰입니다.")
            
        # DB 조회를 생략하고 토큰에서 검증된 UUID를 즉시 반환합니다.
        return user_response.user.id
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"인증 실패: {str(e)}")

# --- Pydantic 모델 정의 ---
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
    group_id: str # UUID 문자열 형태로 변경

# --- API 엔드포인트 구현 ---

@app.get("/")
def read_root():
    return {"message": "수면 서비스 백엔드 서버가 정상 작동 중입니다."}

@app.put("/api/users/nickname")
def set_nickname(request: NicknameRequest, user_id: str = Depends(get_current_user_id)):
    try:
        supabase.table("users").update({"nickname": request.nickname}).eq("id", user_id).execute()
        return {"status": "success", "message": "닉네임이 설정되었습니다."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/groups")
def create_group(request: GroupRequest, user_id: str = Depends(get_current_user_id)):
    try:
        invite_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        group_res = supabase.table("groups").insert({"name": request.group_name, "invite_code": invite_code}).execute()
        group_id = group_res.data[0]['id']
        
        supabase.table("group_member").insert({"group_id": group_id, "user_id": user_id}).execute()
        
        return {
            "status": "success",
            "data": {
                "group_id": str(group_id),
                "invite_code": invite_code
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/groups/join")
def join_group(request: GroupJoinRequest, user_id: str = Depends(get_current_user_id)):
    try:
        group_res = supabase.table("groups").select("id, name").eq("invite_code", request.invite_code).execute()
        if not group_res.data:
            raise ValueError("유효하지 않은 초대 코드입니다.")
            
        group_id = group_res.data[0]['id']
        supabase.table("group_member").insert({"group_id": group_id, "user_id": user_id}).execute()
        
        return {
            "status": "success",
            "data": {
                "group_id": str(group_id),
                "group_name": group_res.data[0]['name']
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/api/users/target-time")
def set_target_time(request: TargetTimeRequest, user_id: str = Depends(get_current_user_id)):
    try:
        supabase.table("users").update({"target_time": request.target_sleep_time}).eq("id", user_id).execute()
        return {"status": "success", "message": "목표 시간이 설정되었습니다."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/home")
def get_home_data(user_id: str = Depends(get_current_user_id)):
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

@app.get("/api/feed")
def get_sleep_feed(user_id: str = Depends(get_current_user_id)):
    try:
        gm_res = supabase.table("group_member").select("group_id").eq("user_id", user_id).execute()
        if not gm_res.data:
            return {"status": "success", "data": []}
            
        group_id = gm_res.data[0]['group_id']
        members_res = supabase.table("group_member").select("user_id").eq("group_id", group_id).execute()
        member_ids = [m['user_id'] for m in members_res.data]
        
        users_res = supabase.table("users").select("id, nickname, current_status").in_("id", member_ids).execute()
        
        feed_data = [{"user_id": str(u['id']), "nickname": u['nickname'], "status": u.get('current_status', 'awake')} for u in users_res.data]
            
        return {"status": "success", "data": feed_data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/users/{target_id}/poke")
def poke_user(target_id: str, user_id: str = Depends(get_current_user_id)):
    try:
        supabase.table("pokes").insert({"sender_id": user_id, "receiver_id": target_id}).execute()
        supabase.table("notifications").insert({
            "user_id": target_id, 
            "type": "poke", 
            "content": "콕 찌르기 알림을 받았습니다.", 
            "is_read": False
        }).execute()
        return {"status": "success", "message": "찌르기 알림을 전송했습니다."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/sleep/start")
def start_sleep(request: SleepStartRequest, user_id: str = Depends(get_current_user_id)):
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

@app.post("/api/sleep/stop")
def stop_sleep(request: SleepStopRequest, user_id: str = Depends(get_current_user_id)):
    try:
        current_time_dt = datetime.now(timezone.utc)
        current_time_iso = current_time_dt.isoformat()
        
        # 1. 수면 시작 기록 조회
        record_res = supabase.table("sleep_records").select("start_time").eq("id", request.session_id).single().execute()
        start_time_dt = datetime.fromisoformat(record_res.data['start_time'].replace('Z', '+00:00'))
        
        # 2. 목표 취침 시각(target_time) 조회
        user_res = supabase.table("users").select("target_time").eq("id", user_id).single().execute()
        target_time_str = user_res.data.get("target_time")
        
        # 3. 목표 달성 여부 판단 (시각 비교 로직)
        is_achieved = False
        if target_time_str:
            target_h, target_m = map(int, target_time_str.split(':'))
            from datetime import time
            target_time_obj = time(target_h, target_m)
            
            actual_time = start_time_dt.time()
            
            # 수면 시작 시각이 목표 시각보다 이전이거나 같으면 성공 처리
            # (주의: 자정 이후 취침 등 복잡한 날짜 경계 계산이 필요할 경우 추가 로직이 요구될 수 있습니다.)
            is_achieved = actual_time <= target_time_obj
        
        # 4. 전체 수면 시간(분) 계산 (리포트 통계용)
        diff = current_time_dt - start_time_dt
        total_minutes = int(diff.total_seconds() // 60)
        
        # 5. DB 데이터 업데이트
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

@app.get("/api/sleep/records/{session_id}")
def get_sleep_record(session_id: str, user_id: str = Depends(get_current_user_id)):
    try:
        record_res = supabase.table("sleep_records").select(
            "start_time, end_time, total_sleep_minutes, is_goal_achieved"
        ).eq("id", session_id).single().execute()
        
        if not record_res.data:
            raise ValueError("해당 수면 기록을 찾을 수 없습니다.")
            
        return {"status": "success", "data": record_res.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/users/me")
def get_my_info(user_id: str = Depends(get_current_user_id)):
    try:
        user_res = supabase.table("users").select("nickname, target_time").eq("id", user_id).single().execute()
        gm_res = supabase.table("group_member").select("group_id").eq("user_id", user_id).execute()
        group_id = str(gm_res.data[0]['group_id']) if gm_res.data else None
        
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

@app.put("/api/users/me")
def update_my_info(request: UserInfoUpdateRequest, user_id: str = Depends(get_current_user_id)):
    try:
        supabase.table("users").update({
            "nickname": request.nickname,
            "target_time": request.target_sleep_time
        }).eq("id", user_id).execute()
        return {"status": "success", "message": "정보가 수정되었습니다."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/api/users/group")
def change_group(request: GroupChangeRequest, user_id: str = Depends(get_current_user_id)):
    try:
        existing = supabase.table("group_member").select("id").eq("user_id", user_id).execute()
        if existing.data:
            supabase.table("group_member").update({"group_id": request.group_id}).eq("user_id", user_id).execute()
        else:
            supabase.table("group_member").insert({"group_id": request.group_id, "user_id": user_id}).execute()
        return {"status": "success", "message": "그룹이 변경되었습니다."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/notifications")
def get_notifications(page: int = 1, user_id: str = Depends(get_current_user_id)):
    try:
        offset = (page - 1) * 10
        noti_res = supabase.table("notifications").select("*").eq("user_id", user_id).order("created_at", desc=True).range(offset, offset + 9).execute()
        return {"status": "success", "data": noti_res.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# KST 타임존 설정 (UTC+9)
KST = timezone(timedelta(hours=9))
# 요일 매핑 배열
WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]

@app.get("/api/reports")
def get_reports(period: str = "weekly", user_id: str = Depends(get_current_user_id)):
    try:
        if period == "weekly":
            # 1. 기준 시간 계산 (현재 시점으로부터 7일 전, UTC 기준)
            now_utc = datetime.now(timezone.utc)
            seven_days_ago = now_utc - timedelta(days=7)
            
            # 2. 데이터베이스 조회 (7일 이내 데이터, 과거순 정렬)
            records_res = supabase.table("sleep_records").select(
                "start_time, is_goal_achieved"
            ).eq("user_id", user_id).gte(
                "start_time", seven_days_ago.isoformat()
            ).order("start_time", desc=False).execute()
            
            # 3. 일별 기록 병합 처리
            daily_records = {}
            
            for record in records_res.data:
                start_time_str = record.get("start_time")
                is_achieved = record.get("is_goal_achieved")
                
                # UTC 문자열을 datetime 객체로 파싱 후 KST로 변환
                dt_utc = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                dt_kst = dt_utc.astimezone(KST)
                
                # 날짜 문자열(YYYY-MM-DD) 추출
                date_key = dt_kst.strftime("%Y-%m-%d")
                
                if date_key not in daily_records:
                    # 해당 날짜의 첫 기록 생성
                    # order("start_time", desc=False)로 인해 가장 이른 수면 시간이 기록됨
                    daily_records[date_key] = {
                        "date": date_key,
                        "weekday": WEEKDAYS[dt_kst.weekday()],
                        "start_time": start_time_str, 
                        "is_goal_achieved": is_achieved
                    }
                else:
                    # 동일 날짜에 추가 기록이 있는 경우 (병합 로직)
                    # 하루 중 한 번이라도 목표에 성공했다면 True로 갱신
                    if is_achieved:
                        daily_records[date_key]["is_goal_achieved"] = True
                        
            # 딕셔너리 값을 리스트로 변환
            report_data = list(daily_records.values())
            
            return {
                "status": "success",
                "data": {
                    "period": "weekly",
                    "records": report_data
                }
            }
        else:
            return {"status": "success", "data": {"period": period, "records": []}}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))