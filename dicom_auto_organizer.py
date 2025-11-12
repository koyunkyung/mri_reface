"""
DICOM Organizer & Renamer (Batch Version)
-----------------------------------------
Author: [작성자 이름 또는 팀명]
Date: [작성일]

기능:
1️⃣ HP* 폴더  → SeriesDescription 기준으로 DICOM 정리 (_organized 폴더 생성)
2️⃣ SA* 폴더  → 숫자 폴더 이름을 SeriesDescription으로 자동 변경
3️⃣ 루트 폴더 한 번 지정으로 모든 하위 폴더 자동 처리

필요 패키지:
    pip install pydicom
"""

from pathlib import Path
import pydicom
import shutil
import re
import os


# -------------------------------------------------------------
# 공통 유틸 함수
# -------------------------------------------------------------
def safe_name(name: str) -> str:
    """폴더명으로 안전하게 변환 (공백·특수문자 → '_')"""
    name = re.sub(r'\s+', '_', str(name).strip())
    name = re.sub(r'[^A-Za-z0-9_\-]', '_', name)
    return name


# -------------------------------------------------------------
# ① HP 폴더: DICOM 파일을 시퀀스별로 정리 (_organized 폴더 생성)
# -------------------------------------------------------------
def organize_dicom_by_series(dicom_dir: Path):
    organized_dir = dicom_dir.parent / (dicom_dir.name + "_organized")
    organized_dir.mkdir(exist_ok=True)
    print(f"\n📂 정리 폴더 생성: {organized_dir}")

    for f in dicom_dir.rglob("*"):
        if not f.is_file():
            continue
        try:
            ds = pydicom.dcmread(f, stop_before_pixels=True)
            series_name = ds.get("SeriesDescription", "UnknownSeries")
            safe_series_name = safe_name(series_name)

            dest_dir = organized_dir / safe_series_name
            dest_dir.mkdir(exist_ok=True)

            shutil.copy2(f, dest_dir / f.name)
            # shutil.move(f, dest_dir / f.name)  # 이동으로 바꾸려면 이 줄 사용

        except Exception as e:
            print(f"⚠️ {f.name} 처리 실패: {e}")

    print("✅ DICOM 시퀀스별 정리 완료!")


# -------------------------------------------------------------
# ② SA 폴더: 숫자 폴더 이름을 SeriesDescription 기반으로 자동 변경
# -------------------------------------------------------------
def rename_numeric_folders_to_series(root_dir: Path):
    print(f"\n🔍 폴더명 변환 대상: {root_dir}")
    for sub_dir in sorted(root_dir.iterdir()):
        if not sub_dir.is_dir():
            continue
        try:
            dcm_files = list(sub_dir.glob("*.dcm"))
            if not dcm_files:
                dcm_files = [f for f in sub_dir.iterdir() if f.is_file()]
            if not dcm_files:
                print(f"⚠️ {sub_dir.name}: DICOM 없음, 건너뜀")
                continue

            first_dcm = dcm_files[0]
            ds = pydicom.dcmread(first_dcm, stop_before_pixels=True)
            series_name = ds.get("SeriesDescription", "UnknownSeries")
            safe_series_name = safe_name(series_name)

            new_dir = sub_dir.parent / safe_series_name

            # 중복 방지
            if new_dir.exists():
                count = 1
                while (sub_dir.parent / f"{safe_series_name}_{count}").exists():
                    count += 1
                new_dir = sub_dir.parent / f"{safe_series_name}_{count}"

            os.rename(sub_dir, new_dir)
            print(f"✅ {sub_dir.name} → {new_dir.name}")

        except Exception as e:
            print(f"⚠️ {sub_dir.name} 처리 실패: {e}")

    print("🎯 폴더 이름 변경 완료!")


# -------------------------------------------------------------
# ③ 루트 디렉터리 자동 처리
# -------------------------------------------------------------
def process_all_folders(root_path: Path):
    """
    루트 경로 아래 HP*, SA* 폴더를 자동 탐색하여 각각의 작업 수행
    """
    print(f"🚀 루트 경로: {root_path}")
    if not root_path.exists():
        print("❌ 지정한 경로가 존재하지 않습니다.")
        return

    hp_folders = sorted([p for p in root_path.glob("HP*") if p.is_dir()])
    sa_folders = sorted([p for p in root_path.glob("SA*") if p.is_dir()])

    print(f"\n📁 HP 폴더 수: {len(hp_folders)}")
    print(f"📁 SA 폴더 수: {len(sa_folders)}")

    # HP 폴더 정리
    for hp_dir in hp_folders:
        print(f"\n=== HP 폴더 처리 중: {hp_dir.name} ===")
        organize_dicom_by_series(hp_dir)

    # SA 폴더 이름 변경
    for sa_dir in sa_folders:
        print(f"\n=== SA 폴더 처리 중: {sa_dir.name} ===")
        rename_numeric_folders_to_series(sa_dir)

    print("\n🎉 전체 처리 완료!")


# -------------------------------------------------------------
# 실행 예시 (루트 폴더만 지정하면 나머지는 자동)
# -------------------------------------------------------------
if __name__ == "__main__":
    base_path = Path("../KAIST_testMR_extracted")
    process_all_folders(base_path)
