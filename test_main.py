import pytest
from httpx import AsyncClient, ASGITransport
import main  # main.py 파일을 가져옵니다.

# 1. 테스트용 설정
BASE_URL = "http://test"
# [중요 ⭐] Supabase 'users' 테이블에 실제로 존재하는 ID여야 합니다.
MOCK_UUID = "16a94e0f-bf6b-4c10-b372-fc32aeb43921" 

# 2. 가짜 인증 함수 (무조건 위 ID를 반환하게 만듦)
async def mock_get_current_user_id():
    return MOCK_UUID

@pytest.mark.asyncio
async def test_full_flow():
    """서버의 모든 기능을 순서대로 테스트합니다."""
    
    # [인증 바꿔치기] 실제 Supabase 로그인을 건너뛰고 가짜 유저로 접속하게 함
    main.app.dependency_overrides[main.get_current_user_id] = mock_get_current_user_id

    async with AsyncClient(transport=ASGITransport(app=main.app), base_url=BASE_URL) as ac:
        headers = {"Authorization": "Bearer any_token"}

        # --- [STEP 1] 서버 연결 확인 ---
        res = await ac.get("/")
        assert res.status_code == 200
        print("\n✅ 서버 연결 성공")

        # --- [STEP 2] 닉네임 설정 ---
        res = await ac.put("/api/users/nickname", 
                          json={"nickname": "테스터123"}, 
                          headers=headers)
        assert res.status_code == 200
        print("✅ 닉네임 설정 성공")

        # --- [STEP 3] 그룹 생성 ---
        res = await ac.post("/api/groups", 
                           json={"group_name": "테스트 수면방"}, 
                           headers=headers)
        assert res.status_code == 200
        group_id = res.json()["data"]["group_id"]
        print(f"✅ 그룹 생성 성공 (ID: {group_id})")

        # --- [STEP 4] 수면 시작 ---
        res = await ac.post("/api/sleep/start", 
                           json={"goodnight_message": "잘 자요!"}, 
                           headers=headers)
        assert res.status_code == 200
        session_id = res.json()["data"]["session_id"]
        print(f"✅ 수면 시작 성공 (세션: {session_id})")

        # --- [STEP 5] 수면 종료 ---
        res = await ac.post("/api/sleep/stop", 
                           json={"session_id": session_id}, 
                           headers=headers)
        assert res.status_code == 200
        assert "is_goal_achieved" in res.json()["data"]
        print("✅ 수면 종료 및 결과 확인 성공")

        # --- [STEP 6] 수면 상세 기록 조회 (신규 API) ---
        res = await ac.get(f"/api/sleep/records/{session_id}", headers=headers)
        assert res.status_code == 200
        print("✅ 수면 상세 데이터 조회 성공")

        # --- [STEP 7] 리포트 조회 ---
        res = await ac.get("/api/reports?period=weekly", headers=headers)
        assert res.status_code == 200
        print(f"✅ 리포트 조회 성공 (달성률: {res.json()['data']['achievement_rate']}%)")

    # 테스트 종료 후 인증 설정 원상복구
    main.app.dependency_overrides = {}

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])