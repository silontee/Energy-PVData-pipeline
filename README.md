# ☀️ Energy-Data-Pipeline (태양광 발전 데이터 파이프라인)

> 공공데이터포털 API를 활용하여 태양광 발전 실적을 수집하고, **Prefect**로 스케줄링/실행 관리, **Grafana**로 시각화하는 데이터 파이프라인입니다.
> 본 프로젝트는 태양광 발전 데이터 증강(Data Augmentation) 연구를 위한 기초 데이터 확보를 목적으로 합니다.

---

## 🏗️ 아키텍처
컨테이너 기준 전체 구성은 아래와 같습니다.

```
            (공공데이터포털 API)
                    │
                    ▼
            pv-worker (Prefect Worker)
                    │  (SQLAlchemy)
                    ▼
          pv-db (PostgreSQL: solar_db)
                    ▲
                    │  (Datasource)
                    ▼
             pv-grafana (Dashboards)

prefect-server (Prefect UI/API) ── uses ── prefect-db (PostgreSQL)
         ▲
         │ (work pool: default-agent-pool)
         └──────────── pv-worker
```

### 🔄 데이터 흐름(요약)
1) `pv-worker`가 API에서 발전 실적 수집
2) 수집 데이터를 `pv-db`의 테이블(`pv_generation`, `plant_info`)에 적재
3) Grafana가 `pv-db`를 조회하여 대시보드로 시각화
4) Prefect는 `prefect-server`에서 스케줄/실행 이력을 관리하며, 내부 DB로 `prefect-db(PostgreSQL)`를 사용합니다.

---

## ⚙️ 사전 준비
- Docker Desktop
- (선택) 로컬에서 Prefect CLI를 실행할 경우 Python + `uv`

---

## 🔐 환경 변수(.env) 설정
`.env.example`을 복사해 `.env`를 만들고 값을 채워주세요.

```powershell
copy .env.example .env
```

필수 키:
- `NAMBU_API_KEY`: 공공데이터포털 서비스 키
- `DB_USER`, `DB_PASS`, `DB_NAME`: PV 데이터베이스(pv-db) 계정 정보
- `PREFECT_DB_USER`, `PREFECT_DB_PASS`, `PREFECT_DB_NAME`: Prefect 내부 DB(prefect-db) 계정 정보
- `GRAFANA_USER`, `GRAFANA_PASS`: Grafana 계정 정보

로컬에서 Prefect CLI 실행 시(터미널 세션에만 적용):
- `PREFECT_API_URL=http://127.0.0.1:4200/api`

---

## 🌐 서비스 접속 정보

| 서비스 | 주소 | 비고 |
|---|---|---|
| Prefect UI | http://127.0.0.1:4200 | 배포/실행 이력, 스케줄 확인 |
| Grafana | http://127.0.0.1:3002 | 대시보드 확인 (초기 ID/PW: `admin/admin`) |
| PV DB(Postgres) | 127.0.0.1:5432 | 로컬 DB 툴로 접근 시 |

---

## 🚀 실행 순서 (처음부터)

### 1) Docker 컨테이너 기동
```powershell
docker compose up -d --build
```

### 2) Prefect 배포 등록 (처음 1회 또는 스케줄/엔트리포인트 변경 시)
> 아래 두 줄은 “현재 터미널”에서만 Prefect 서버 주소를 지정한 뒤, 배포를 등록하는 과정입니다.

```powershell
$env:PREFECT_API_URL="http://127.0.0.1:4200/api"
uv run prefect deploy
```

### 3) 수동 실행 테스트 (선택)
```powershell
$env:PREFECT_API_URL="http://127.0.0.1:4200/api"
uv run prefect deployment run "Daily Solar Automation/Daily-Solar-Sync"
```

### 4) 로그 확인
```powershell
docker compose logs -f pv-worker
docker compose logs -f prefect-server
```

---

## 🛠️ 초기 데이터 적재 (필요 시)
과거 데이터/마스터 데이터를 처음 구성해야 할 때만 실행합니다.

### ⚠️ (중요) 공공데이터포털 파일 다운로드
초기 적재 단계에서 “설비 사양/발전소 정보” CSV가 필요할 수 있습니다.
아래 링크에서 본인 계정으로 로그인 후 제공 파일을 다운로드해 프로젝트 루트에 저장하세요.

- 다운로드 링크: https://www.data.go.kr/iim/dps/dpc/selectMyDataPrcusView.do
- 저장 위치: 프로젝트 루트(예: `C:\pv_progect\Energy-PVData-pipeline\`)
- 파일명이 다르면: `scripts/initial_db_ingestion.py`의 `SPECS_FILE` 경로를 다운로드한 파일명으로 수정

### 적재 단계
1) 시작일 탐색
```powershell
uv run python scripts/nambu_probe_date.py
```

2) 과거 데이터 수집
```powershell
uv run python scripts/nambu_bulk_sync.py
```

3) 데이터 정리/병합
```powershell
uv run python scripts/nambu_merge_pv_data.py
```

4) DB 적재
```powershell
uv run python scripts/initial_db_ingestion.py
```

5) 적재 확인
```powershell
uv run python scripts/inspect_both_table.py
```

---

## 📊 Grafana에서 확인할 수 있는 것들
Grafana는 `pv-db`를 datasource로 사용합니다(프로비저닝: `grafana/provisioning/datasources/datasource.yml`).

추천 대시보드/패널 아이디어:
- 발전량 시계열(시간대별): 발전소(`ipptnm`), 호기(`hogi`)별 `generation` 추이
- 일/주/월 집계: 날짜별 합계/평균/최대 발전량
- 발전소 비교: 여러 발전소를 한 그래프에서 비교(Top N)
- 결측/이상치 탐지: 특정 날짜/시간대에 발전량이 0으로 고정되는 구간 찾기
- 최신 수집 상태: “최근 n일간 데이터가 들어왔는지” 확인(마지막 `timestamp` 기준)

---

## ⏰ Prefect 자동 실행(스케줄)
- 스케줄은 `prefect.yaml`에 정의되어 있으며 “매일 09:00(Asia/Seoul)” 실행을 목표로 합니다.
- `uv run prefect deploy`는 **최초 1회** 또는 **스케줄/엔트리포인트 변경 시** 다시 실행하면 됩니다.

---

## 🧩 트러블슈팅
- Prefect UI가 빈 화면/`ERR_EMPTY_RESPONSE`: 서버 초기화(의존성 설치) 중일 수 있으니 1~2분 대기 후 재접속
- `database is locked`: Prefect 내부 DB가 SQLite를 쓸 때 발생할 수 있으며, 본 프로젝트는 `prefect-db(PostgreSQL)`를 사용하도록 구성되어 있습니다.
- Work pool이 없다는 경고: `pv-worker` 컨테이너를 먼저 띄우면 `default-agent-pool`이 자동 생성됩니다.
