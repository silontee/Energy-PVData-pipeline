import asyncio
import aiohttp
import pandas as pd
import xml.etree.ElementTree as ET
import os
from pathlib import Path
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from prefect import flow, task
from dotenv import load_dotenv

# 1. 환경 설정 로드 (현재 위치: automation/ 폴더)
load_dotenv()
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

API_KEY = os.getenv("NAMBU_API_KEY")
ENDPOINT = "https://apis.data.go.kr/B552520/PwrSunLightInfo/getDataService"
DB_URL = os.getenv("DB_URL") or os.getenv("LOCAL_DB_URL")

engine = create_engine(DB_URL)

# --- [Task 1: 수집 대상 분석] ---
@task(name="Get Active Targets", log_prints=True)
def get_active_targets():
    """정제된 plant_name 컬럼을 기준으로 마지막 수집일 확인"""
    query = """
    SELECT 
        p.gencd, p.hogi, p.plant_name, 
        MAX(g.timestamp) as last_date
    FROM plant_info p
    LEFT JOIN pv_generation g ON p.gencd = g.gencd AND p.hogi = g.hogi
    GROUP BY p.gencd, p.hogi, p.plant_name
    """
    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn)
    
    active_targets = []
    yesterday = datetime.now() - timedelta(days=1)

    for _, row in df.iterrows():
        last_date = row['last_date']
        
        # 2025년 이전 데이터만 있다면 가동 중단으로 간주
        if last_date and last_date.year < 2025:
            continue
            
        # 마지막 기록 다음날부터 수집 시작
        start_dt = (last_date + timedelta(days=1)) if last_date else (datetime.now() - timedelta(days=365))
        
        if start_dt.date() <= yesterday.date():
            active_targets.append({
                'gencd': str(row['gencd']),
                'hogi': str(row['hogi']),
                'plant_name': row['plant_name'],
                'start_dt': start_dt
            })
    return active_targets

# --- [Task 2: API 데이터 수집] ---
async def fetch_api_data(session, date_str, gencd, hogi):
    params = {
        "serviceKey": API_KEY, "pageNo": "1", "numOfRows": "100",
        "strSdate": date_str, "strEdate": date_str,
        "strOrgCd": gencd, "strHoki": hogi
    }
    try:
        async with session.get(ENDPOINT, params=params, timeout=15) as response:
            if response.status != 200: return None
            root = ET.fromstring(await response.text())
            items = root.find('.//items')
            return {child.tag: child.text for child in items} if items is not None else None
    except:
        return None

@task(name="Collect and Save Solar Data", log_prints=True)
async def collect_and_save(targets):
    yesterday = datetime.now() - timedelta(days=1)
    total_rows = 0

    async with aiohttp.ClientSession() as session:
        for target in targets:
            date_list = pd.date_range(start=target['start_dt'], end=yesterday).strftime("%Y%m%d").tolist()
            if not date_list: continue

            print(f"📡 {target['plant_name']} ({target['hogi']}호기) {len(date_list)}일분 수집 중...")
            
            raw_data = []
            for d_str in date_list:
                data = await fetch_api_data(session, d_str, target['gencd'], target['hogi'])
                if data:
                    data['gencd'], data['hogi'] = target['gencd'], target['hogi']
                    raw_data.append(data)
                await asyncio.sleep(0.05)

            if raw_data:
                df_raw = pd.DataFrame(raw_data)
                v_vars = [c for c in df_raw.columns if c.startswith('qhorgen')]
                df_long = df_raw.melt(id_vars=['ymd', 'hogi', 'gencd'], value_vars=v_vars, 
                                     var_name='h_str', value_name='generation')
                
                df_long['hour'] = df_long['h_str'].str.extract(r'(\d+)').astype(int)
                df_long['timestamp'] = pd.to_datetime(df_long['ymd']) + pd.to_timedelta(df_long['hour'], unit='h')
                df_long['generation'] = pd.to_numeric(df_long['generation'], errors='coerce').fillna(0)
                df_long['ipptnm'] = target['plant_name']

                final_df = df_long[['timestamp', 'ipptnm', 'hogi', 'generation', 'gencd']]
                
                with engine.begin() as conn:
                    final_df.to_sql('pv_generation', con=conn, if_exists='append', index=False)
                
                total_rows += len(final_df)
                print(f"   ㄴ ✅ {len(final_df)}행 저장 완료")
    return total_rows

# --- [Flow] ---
@flow(name="Daily Solar Automation", log_prints=True)
def solar_automation_flow():
    targets = get_active_targets()
    if targets:
        asyncio.run(collect_and_save(targets))
    else:
        print("☀️ 최신 상태입니다.")

if __name__ == "__main__":
    solar_automation_flow()
