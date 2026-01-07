import pandas as pd
import os
import re
from sqlalchemy import create_engine, text
from pathlib import Path
from dotenv import load_dotenv

# 1. 환경 설정 및 DB 연결
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

DB_URL = os.getenv("LOCAL_DB_URL") 
engine = create_engine(DB_URL)

# --- [정제 로직] ---
def clean_name(name):
    if pd.isna(name): return ""
    name = str(name).replace("한국남부발전(주)_", "").replace("태양광발전실적", "").replace("태양광", "").replace("발전소", "")
    return re.sub(r'\s+', '', name)

def extract_specs(text_val):
    if pd.isna(text_val): return None, None
    mod_match = re.search(r'모듈\s*:\s*(.*?)(?=인버터|$)', str(text_val))
    inv_match = re.search(r'인버터\s*:\s*(.*)', str(text_val))
    mod = mod_match.group(1).strip() if mod_match else None
    inv = inv_match.group(1).strip() if inv_match else None
    return mod, inv

def clean_number(text_val):
    if pd.isna(text_val): return None
    # 콤마(,) 제거 후 숫자 추출
    text_val = str(text_val).replace(",", "")
    match = re.search(r'(\d+\.?\d*)', text_val)
    return float(match.group(1)) if match else None

# --- [수동 위경도 및 상세 사양 데이터 (사용자 제공 정보 반영)] ---
MANUAL_PLANT_DATA = [
    # 부산수처리장 (997Q)
    {'gcd': '997Q', 'hg': '1', 'lat': 35.2591938, 'lon': 129.2235041, 'addr': '부산광역시 사하구 감천항로 7(감천동)', 'cap': 110.5, 'ang': 25, 'mod': '340Wⅹ325', 'inv': '100kW, 10.5kW'},
    
    # 부산본부 (B997) - 1, 2호기 공통
    {'gcd': 'B997', 'hg': '1', 'lat': 35.0870019, 'lon': 128.9989357, 'addr': '부산광역시 사하구 감천항로 7(감천동)', 'cap': 1400.475, 'ang': 25, 'mod': '355Wⅹ3,945', 'inv': '500kWⅹ3EA'},
    {'gcd': 'B997', 'hg': '2', 'lat': 35.0870019, 'lon': 128.9989357, 'addr': '부산광역시 사하구 감천항로 7(감천동)', 'cap': 1400.475, 'ang': 25, 'mod': '355Wⅹ3,945', 'inv': '500kWⅹ3EA'},
    
    # 신인천전망대 (997S)
    {'gcd': '997S', 'hg': '1', 'lat': 37.536111, 'lon': 126.602318, 'addr': '인천광역시 서구 장도로 57 (청라동)', 'cap': 1742, 'ang': 20, 'mod': '475W x 3,668', 'inv': '250kW x 7EA'},
    
    # 신인천해수구취수구 (997Y)
    {'gcd': '997Y', 'hg': '1', 'lat': 37.536111, 'lon': 126.602318, 'addr': '인천광역시 서구 장도로 57 (청라동)', 'cap': 907.2, 'ang': 23, 'mod': '360W x 2,520', 'inv': '250kW x 4EA'},
    
    # 삼척소내 (S997) - 1, 2, 3호기 개별 용량 반영
    {'gcd': 'S997', 'hg': '1', 'lat': 37.1902416, 'lon': 129.3387384, 'addr': '강원도 삼척시 원덕읍 삼척로 734', 'cap': 999, 'ang': 25, 'mod': '360Wⅹ2,775', 'inv': '500kWⅹ2EA'},
    {'gcd': 'S997', 'hg': '2', 'lat': 37.1902416, 'lon': 129.3387384, 'addr': '강원도 삼척시 원덕읍 삼척로 734', 'cap': 990.45, 'ang': 25, 'mod': '355Wⅹ2,790', 'inv': '500kWⅹ2EA'},
    {'gcd': 'S997', 'hg': '3', 'lat': 37.1902416, 'lon': 129.3387384, 'addr': '강원도 삼척시 원덕읍 삼척로 734', 'cap': 2002.32, 'ang': 25, 'mod': '360Wⅹ5,562', 'inv': '500kWⅹ1EA, 1500kW x 1EA'},

    # 기타 기존 데이터 유지
    {'gcd': '997D', 'hg': '1', 'lat': 33.2373862, 'lon': 126.3418842, 'mod': '250W x 784', 'inv': '100kW x 2EA'},
    {'gcd': '997G', 'hg': '1', 'lat': 35.0586428, 'lon': 128.8157557, 'mod': '144Wp x 272, 100Wp x 384, 215Wp x 176', 'inv': '20kW x 6EA'},
    {'gcd': '997N', 'hg': '1', 'lat': 35.0586428, 'lon': 128.8157557, 'mod': '300Wⅹ624', 'inv': '100kW x 2EA'},
    {'gcd': '9987', 'hg': '1', 'lat': 35.1157106, 'lon': 129.0428212, 'mod': '400W x 2086', 'inv': '500kW x 2EA'},
    {'gcd': '8760', 'hg': '1', 'lat': 37.536111, 'lon': 126.602318, 'mod': '250W x 800', 'inv': '210kW x 1EA'},
    {'gcd': '9985', 'hg': '1', 'lat': 37.536111, 'lon': 126.602318, 'mod': '390W X 1,545', 'inv': '100kW x 6EA, 34kW x 1EA'},
    {'gcd': '9988', 'hg': '1', 'lat': 37.536111, 'lon': 126.602318, 'mod': '450W x 672', 'inv': '100kW x 3EA'},
    {'gcd': '9989', 'hg': '1', 'lat': 37.536111, 'lon': 126.602318, 'mod': '450W x 658', 'inv': '100kW x 3EA'},
    {'gcd': '9979', 'hg': '1', 'lat': 37.3335822, 'lon': 127.4795795, 'mod': '440W x 2272', 'inv': '500kW X 2EA'}
]

def run_ingestion():
    PROCESSED_DIR = PROJECT_ROOT / "pv_data_processed"
    SPECS_FILE = PROJECT_ROOT / "한국남부발전(주)_태양광발전기 사양정보_20250630.csv"
    files = sorted(list(PROCESSED_DIR.glob("nambu_processed_*.csv")))
    
    if not files:
        print("❌ 가공된 CSV 파일이 없습니다.")
        return

    # --- 1단계: 테이블 초기화 ---
    print("🧹 1. 테이블 초기화 중...")
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS pv_generation CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS plant_info CASCADE;"))
        conn.execute(text("""
            CREATE TABLE pv_generation (
                timestamp TIMESTAMP NOT NULL,
                ipptnm TEXT NOT NULL,
                hogi TEXT NOT NULL,
                generation FLOAT,
                gencd TEXT,
                PRIMARY KEY (timestamp, ipptnm, hogi)
            );
        """))

    # --- 2단계: 마스터 데이터 구축 ---
    print("🏠 2. 마스터 테이블(plant_info) 구축 중...")
    sample_dfs = []
    for f in files:
        df_tmp = pd.read_csv(f, encoding='utf-8-sig').iloc[:1]
        sample_dfs.append(df_tmp)
    df_master = pd.concat(sample_dfs).drop_duplicates(['gencd', 'hogi'])
    df_master['clean_name'] = df_master['ipptnm'].apply(clean_name)

    # 사양정보 CSV 로드
    if SPECS_FILE.exists():
        df_specs = pd.read_csv(SPECS_FILE, encoding='cp949')
        df_specs['clean_name'] = df_specs['발전소명'].apply(clean_name)
        df_specs['csv_cap'] = df_specs['설치용량'].apply(clean_number)
        df_specs['csv_ang'] = df_specs['설치각'].apply(clean_number)
        df_specs[['csv_mod', 'csv_inv']] = df_specs['설치용량'].apply(lambda x: pd.Series(extract_specs(x)))
        df_master = pd.merge(df_master, df_specs, on='clean_name', how='left')

    # 수동 데이터 병합 (우선순위 높음)
    df_master['hogi'] = df_master['hogi'].astype(str)
    df_master['gencd'] = df_master['gencd'].astype(str)
    df_manual = pd.DataFrame(MANUAL_PLANT_DATA)
    df_manual['hg'] = df_manual['hg'].astype(str)
    df_manual['gcd'] = df_manual['gcd'].astype(str)
    df_master = pd.merge(df_master, df_manual, left_on=['gencd', 'hogi'], right_on=['gcd', 'hg'], how='left')

    # 최종 데이터 우선순위 결정 (수동 > CSV > 기본)
    df_master['final_addr'] = df_master['addr'].fillna(df_master['발전소 주소지_y']).fillna(df_master['발전소 주소지_x'])
    df_master['final_cap'] = df_master['cap'].fillna(df_master.get('csv_cap')).fillna(df_master['설치용량_x'].apply(clean_number))
    df_master['final_ang'] = df_master['ang'].fillna(df_master.get('csv_ang')).fillna(df_master['설치각_x'].apply(clean_number))
    df_master['final_mod'] = df_master['mod'].fillna(df_master.get('csv_mod'))
    df_master['final_inv'] = df_master['inv'].fillna(df_master.get('csv_inv'))

    master_cols_map = {
        'gencd': 'gencd', 'hogi': 'hogi', 'ipptnm': 'plant_name',
        'final_addr': 'address', 'final_cap': 'capacity_kw',
        'final_ang': 'angle_deg', 'lat': 'lat', 'lon': 'lon',
        'final_mod': 'module_spec', 'final_inv': 'inverter_spec'
    }
    
    df_master_final = df_master[list(master_cols_map.keys())].rename(columns=master_cols_map)
    df_master_final.to_sql('plant_info', con=engine, if_exists='replace', index=False)
    print("✅ 마스터 테이블 적재 완료")

    # --- 3단계: 시계열 데이터 적재 ---
    print(f"📈 3. 시계열 데이터 적재 중...")
    for file_path in files:
        df = pd.read_csv(file_path, encoding='utf-8-sig')
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['generation'] = pd.to_numeric(df['generation'], errors='coerce').fillna(0)
        df['hogi'] = df['hogi'].astype(str)
        df = df.drop_duplicates(subset=['timestamp', 'ipptnm', 'hogi'], keep='first')
        df[['timestamp', 'ipptnm', 'hogi', 'generation', 'gencd']].to_sql('pv_generation', con=engine, if_exists='append', index=False)
    
    print("\n🎉 모든 데이터가 성공적으로 저장되었습니다!")

if __name__ == "__main__":
    run_ingestion()