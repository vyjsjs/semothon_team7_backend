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

class PokeRequest(BaseModel):
    targetUserId: str

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
        # 1. 초대 코드 유효성 검증
        group_res = supabase.table("groups").select("id, name").eq("invite_code", request.invite_code).execute()
        if not group_res.data:
            raise ValueError("유효하지 않은 초대 코드입니다.")
            
        group_id = group_res.data[0]['id']
        
        # 2. 기존 그룹 가입 여부 확인 및 분기 처리
        existing = supabase.table("group_member").select("id").eq("user_id", user_id).execute()
        if existing.data:
            supabase.table("group_member").update({"group_id": group_id}).eq("user_id", user_id).execute()
        else:
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
        
        # 수정된 부분: 응답 데이터의 키를 'status'에서 'current_status'로 변경하여 다른 API와 통일합니다.
        feed_data = [{"user_id": str(u['id']), "nickname": u['nickname'], "current_status": u.get('current_status', 'awake')} for u in users_res.data]
            
        return {"status": "success", "data": feed_data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/poke")
def poke_user(request: PokeRequest, user_id: str = Depends(get_current_user_id)):
    try:
        target_id = request.targetUserId
        
        # 찌르기 기록 추가
        supabase.table("pokes").insert({
            "sender_id": user_id, 
            "receiver_id": target_id
        }).execute()
        
        # 알림 기록 추가
        supabase.table("notifications").insert({
            "user_id": target_id, 
            "type": "poke", 
            "content": "콕 찌르기 알림을 받았습니다.", 
            "is_read": False
        }).execute()
        
        return {"status": "success", "message": "찌르기 알림을 전송했습니다."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/poke/notification")
def check_poke_notification(user_id: str = Depends(get_current_user_id)):
    try:
        # 1. 읽지 않은 찌르기 알림이 있는지 확인
        noti_res = supabase.table("notifications").select("id").eq("user_id", user_id).eq("type", "poke").eq("is_read", False).order("created_at", desc=True).limit(1).execute()
        
        # 미확인 알림이 없을 경우 null 반환
        if not noti_res.data:
            return {"status": "success", "data": None}
            
        # 2. pokes 테이블에서 가장 최근에 나를 찌른 사용자 ID 조회
        poke_res = supabase.table("pokes").select("sender_id").eq("receiver_id", user_id).order("created_at", desc=True).limit(1).execute()
        
        if not poke_res.data:
             return {"status": "success", "data": None}
             
        sender_id = poke_res.data[0]['sender_id']
        
        # 발신자의 닉네임 조회
        sender_res = supabase.table("users").select("nickname").eq("id", sender_id).single().execute()
        sender_nickname = sender_res.data.get("nickname")
        
        # 3. 알림을 읽음 처리로 업데이트
        supabase.table("notifications").update({"is_read": True}).eq("id", noti_res.data[0]['id']).execute()
        
        return {
            "status": "success",
            "data": {
                "fromNickname": sender_nickname
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/sleep/start")
def start_sleep(request: SleepStartRequest, user_id: str = Depends(get_current_user_id)):
    try:
        # 1. 진행 중인 수면 세션 존재 여부 확인
        existing_res = supabase.table("sleep_records").select("id, start_time").eq(
            "user_id", user_id
        ).eq("status", "sleeping").is_("end_time", "null").execute()
        
        if existing_res.data:
            # 수정된 부분: 기존 세션이 존재하더라도 users 테이블의 상태를 sleeping으로 확실히 업데이트합니다.
            supabase.table("users").update({"current_status": "sleeping"}).eq("id", user_id).execute()
            
            return {
                "status": "success",
                "data": {
                    "session_id": str(existing_res.data[0]['id']),
                    "start_time": existing_res.data[0]['start_time'],
                    "message": "기존 진행 중인 수면 기록을 반환합니다."
                }
            }

        # 2. 새로운 수면 기록 생성
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
        
        record_res = supabase.table("sleep_records").select("start_time").eq("id", request.session_id).single().execute()
        start_time_utc = datetime.fromisoformat(record_res.data['start_time'].replace('Z', '+00:00'))
        
        user_res = supabase.table("users").select("target_time").eq("id", user_id).single().execute()
        target_time_str = user_res.data.get("target_time")
        
        is_achieved = False
        if target_time_str:
            target_h, target_m = map(int, target_time_str.split(':'))
            
            # 1. 수면 시작 시각을 KST(한국 표준시)로 변환
            KST = timezone(timedelta(hours=9))
            start_time_kst = start_time_utc.astimezone(KST)
            
            # 2. 자정 경계 오류 방지를 위한 12시간 시프트(Shift) 계산
            shifted_start_hour = (start_time_kst.hour - 12) % 24
            shifted_target_hour = (target_h - 12) % 24
            
            shifted_start_minutes = shifted_start_hour * 60 + start_time_kst.minute
            shifted_target_minutes = shifted_target_hour * 60 + target_m
            
            is_achieved = shifted_start_minutes <= shifted_target_minutes
        
        diff = current_time_dt - start_time_utc
        total_minutes = int(diff.total_seconds() // 60)
        
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
            now_utc = datetime.now(timezone.utc)
            seven_days_ago = now_utc - timedelta(days=7)
            
            records_res = supabase.table("sleep_records").select(
                "start_time, is_goal_achieved"
            ).eq("user_id", user_id).gte(
                "start_time", seven_days_ago.isoformat()
            ).order("start_time", desc=False).execute()
            
            daily_records = {}
            
            for record in records_res.data:
                start_time_str = record.get("start_time")
                is_achieved = record.get("is_goal_achieved")
                
                dt_utc = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                dt_kst = dt_utc.astimezone(KST)
                
                date_key = dt_kst.strftime("%Y-%m-%d")
                
                if date_key not in daily_records:
                    daily_records[date_key] = {
                        "date": date_key,
                        "weekday": WEEKDAYS[dt_kst.weekday()],
                        "start_time": start_time_str, 
                        "is_goal_achieved": is_achieved
                    }
                else:
                    if is_achieved:
                        daily_records[date_key]["is_goal_achieved"] = True
            
            report_data = list(daily_records.values())
            
            # --- 주간 달성률 계산 로직 추가 ---
            valid_days = len(report_data) # 데이터가 존재하는 일수
            achieved_days = sum(1 for record in report_data if record.get("is_goal_achieved")) # 성공한 일수
            
            # 데이터 공백 제외 달성률 계산 (정수형)
            achievement_rate = int((achieved_days / valid_days) * 100) if valid_days > 0 else 0
            
            return {
                "status": "success",
                "data": {
                    "period": "weekly",
                    "records": report_data,
                    "achievement_rate": achievement_rate,
                    "valid_days": valid_days,
                    "achieved_days": achieved_days
                }
            }
        else:
            return {"status": "success", "data": {"period": period, "records": [], "achievement_rate": 0}}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/groups/my")
def get_my_groups(user_id: str = Depends(get_current_user_id)):
    try:
        # 1. group_member 테이블에서 사용자가 속한 그룹 ID 및 가입일 조회
        gm_res = supabase.table("group_member").select(
            "group_id, joined_at"
        ).eq("user_id", user_id).execute()
        
        # 소속된 그룹이 없는 경우 빈 리스트 반환
        if not gm_res.data:
            return {"status": "success", "data": []}
            
        group_ids = [str(gm['group_id']) for gm in gm_res.data]
        
        # 2. groups 테이블에서 해당 그룹들의 상세 정보(이름, 초대코드) 조회
        groups_res = supabase.table("groups").select(
            "id, name, invite_code"
        ).in_("id", group_ids).execute()
        
        # 그룹 정보를 ID를 키로 하는 딕셔너리로 변환 (빠른 매핑을 위함)
        groups_dict = {str(g['id']): g for g in groups_res.data}
        
        group_list = []
        for gm in gm_res.data:
            g_id = str(gm['group_id'])
            if g_id in groups_dict:
                group_list.append({
                    "group_id": g_id,
                    "group_name": groups_dict[g_id]['name'],
                    "invite_code": groups_dict[g_id]['invite_code'],
                    "joined_at": gm.get('joined_at')
                })
                
        return {
            "status": "success",
            "data": group_list
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))