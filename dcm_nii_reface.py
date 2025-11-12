import os
import argparse
import shutil
import re
import subprocess
import pandas as pd
import pydicom
import dicom2nifti
from dicom2nifti import convert_dicom
import logging
import tempfile
import gzip
import numpy as np
from pathlib import Path

logging.getLogger('dicom2nifti').setLevel(logging.CRITICAL)


# ============================================================
# 데이터 전처리 함수들
# ============================================================
def safe_name(name: str) -> str:
    """폴더명을 안전하게 변환"""
    name = re.sub(r'\s+', '_', str(name).strip())
    name = re.sub(r'[^A-Za-z0-9_\-]', '_', name)
    return name


def organize_hp_folder(hp_dir: Path, organized_parent: Path):
    """HP 폴더: SeriesDescription별로 DICOM 정리"""
    organized_dir = organized_parent / hp_dir.name
    organized_dir.mkdir(exist_ok=True)
    print(f"\n📂 HP 폴더 정리: {hp_dir.name} → {organized_dir}")
    
    for f in hp_dir.rglob("*"):
        if not f.is_file():
            continue
        try:
            ds = pydicom.dcmread(f, stop_before_pixels=True)
            series_name = ds.get("SeriesDescription", "UnknownSeries")
            safe_series_name = safe_name(series_name)
            
            dest_dir = organized_dir / safe_series_name
            dest_dir.mkdir(exist_ok=True)
            shutil.copy2(f, dest_dir / f.name)
        except Exception as e:
            print(f"⚠️ {f.name} 처리 실패: {e}")
    
    print(f"✅ {hp_dir.name} 정리 완료")
    return organized_dir


def organize_sa_folder(sa_dir: Path, organized_parent: Path):
    """SA 폴더: 숫자 폴더명 → SeriesDescription 변환"""
    organized_dir = organized_parent / sa_dir.name
    organized_dir.mkdir(exist_ok=True)
    print(f"\n📂 SA 폴더 정리: {sa_dir.name} → {organized_dir}")
    
    for sub_dir in sorted(sa_dir.iterdir()):
        if not sub_dir.is_dir():
            continue
        
        dcm_files = list(sub_dir.glob("*.dcm"))
        if not dcm_files:
            dcm_files = [f for f in sub_dir.iterdir() if f.is_file()]
        if not dcm_files:
            continue
        
        try:
            ds = pydicom.dcmread(dcm_files[0], stop_before_pixels=True)
            series_name = ds.get("SeriesDescription", "UnknownSeries")
            safe_series_name = safe_name(series_name)
            
            new_dir = organized_dir / safe_series_name
            count = 1
            while new_dir.exists():
                new_dir = organized_dir / f"{safe_series_name}_{count}"
                count += 1
            
            shutil.copytree(sub_dir, new_dir)
            print(f"  ✅ {sub_dir.name} → {new_dir.name}")
        except Exception as e:
            print(f"  ⚠️ {sub_dir.name} 처리 실패: {e}")
    
    print(f"✅ {sa_dir.name} 정리 완료")
    return organized_dir


def preprocess_dicom_folders(input_root: Path):
    """HP*/SA* 폴더 자동 탐지 및 전처리"""
    print("\n" + "="*60)
    print("🔧 STEP 1: DICOM 전처리 시작")
    print("="*60)
    
    preprocessed_root = input_root.parent / f"{input_root.name}_preprocessed"
    preprocessed_root.mkdir(exist_ok=True)
    
    hp_folders = sorted([p for p in input_root.glob("HP*") if p.is_dir()])
    sa_folders = sorted([p for p in input_root.glob("SA*") if p.is_dir()])
    
    print(f"📁 HP 폴더: {len(hp_folders)}개")
    print(f"📁 SA 폴더: {len(sa_folders)}개")
    
    processed_folders = []
    
    for hp_dir in hp_folders:
        organized = organize_hp_folder(hp_dir, preprocessed_root)
        processed_folders.append(organized)
    
    for sa_dir in sa_folders:
        organized = organize_sa_folder(sa_dir, preprocessed_root)
        processed_folders.append(organized)
    
    print(f"\n✅ 전처리 완료: {preprocessed_root}")
    return preprocessed_root


# ============================================================
# NIfTI 변환 및 Defacing 함수들
# ============================================================
def clean_filename(text):
    if not text:
        return "UnknownDescription"
    text = re.sub(r'[^a-zA-Z0-9_]', '_', text)
    text = re.sub(r'_+', '_', text)
    return text.strip('_')


def get_image_type(filename):
    name = filename.upper()
    if 'FLAIR' in name: return 'FLAIR'
    if 'T1' in name: return 'T1'
    if 'T2' in name: return 'T2'
    if 'PD' in name: return 'PD'
    if 'FDG' in name: return 'FDG'
    if 'CT' in name: return 'CT'
    return None


def attempt_rescue_conversion(series_folder_path, temp_output_dir):
    """슬라이스 간격 불일치 시 가장 긴 연속 블록 변환"""
    print("      -> 🧠 구조 모드: 연속 슬라이스 블록 탐색...")
    dicom_slices = []
    
    for filename in os.listdir(series_folder_path):
        filepath = os.path.join(series_folder_path, filename)
        if not filepath.lower().endswith('.dcm'):
            continue
        try:
            dcm = pydicom.dcmread(filepath, stop_before_pixels=True)
            if 'ImagePositionPatient' in dcm and 'InstanceNumber' in dcm:
                dicom_slices.append({
                    'path': filepath,
                    'pos': dcm.ImagePositionPatient,
                    'inst': dcm.InstanceNumber
                })
        except:
            continue
    
    if len(dicom_slices) < 5:
        print("      -> ❌ 유효 슬라이스 부족")
        return None
    
    dicom_slices.sort(key=lambda s: s['pos'][2])
    increments = [np.linalg.norm(np.array(dicom_slices[i+1]['pos']) - np.array(dicom_slices[i]['pos'])) 
                  for i in range(len(dicom_slices)-1)]
    
    if not increments:
        return None
    
    longest_group = []
    current_group = [dicom_slices[0]]
    
    for i in range(len(increments)):
        if np.isclose(increments[i], increments[i-1] if i > 0 else increments[i]):
            current_group.append(dicom_slices[i+1])
        else:
            if len(current_group) > len(longest_group):
                longest_group = current_group
            current_group = [dicom_slices[i+1]]
    
    if len(current_group) > len(longest_group):
        longest_group = current_group
    
    if len(longest_group) < 5:
        print("      -> ❌ 연속 그룹이 너무 짧음")
        return None
    
    print(f"      -> ✅ {len(longest_group)}개 슬라이스 발견, 변환 시도")
    try:
        dicom_objects = [pydicom.dcmread(s['path']) for s in longest_group]
        temp_nii_path = os.path.join(temp_output_dir, "rescued_temp.nii.gz")
        convert_dicom.dicom_array_to_nifti(dicom_objects, temp_nii_path, reorient=True)
        return temp_nii_path
    except Exception as e:
        print(f"      -> ❌ 구조 변환 실패: {e}")
        return None


def process_patient_data(input_root, output_root, reface_script_path, save_qc):
    """NIfTI 변환 + Defacing 메인 함수"""
    print("\n" + "="*60)
    print("🚀 STEP 2: NIfTI 변환 및 Defacing 시작")
    print("="*60)
    
    if not os.path.isfile(reface_script_path):
        print(f"🚨 오류: reface_script_path가 파일이 아닙니다: {reface_script_path}")
        return
    
    # Apple Silicon 호환성 패치
    temp_reface_script_path = None
    executable_script_path = reface_script_path
    
    try:
        with open(reface_script_path, 'r') as f:
            script_content = f.read()
        platform_flag = "--platform linux/amd64"
        
        if platform_flag not in script_content:
            print("  - 🔧 Apple Silicon 패치 적용...")
            target_line = "docker run --rm -ti --mount"
            replacement_line = f"docker run --rm -ti {platform_flag} --mount"
            script_content = script_content.replace(target_line, replacement_line)
            
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.sh') as temp_script:
                temp_script.write(script_content)
                temp_reface_script_path = temp_script.name
            
            os.chmod(temp_reface_script_path, 0o755)
            executable_script_path = temp_reface_script_path
    except Exception as e:
        print(f"  - ⚠️ 패치 실패: {e}")
    
    # 환자별 처리
    for patient_folder_name in os.listdir(input_root):
        patient_folder_path = os.path.join(input_root, patient_folder_name)
        if not os.path.isdir(patient_folder_path):
            continue
        
        try:
            patient_id = patient_folder_name.split('_')[0]
            print(f"\n{'='*60}\n🧠 환자 처리: {patient_id}\n{'='*60}")
            
            patient_out_dir = os.path.join(output_root, patient_id)
            original_dir = os.path.join(patient_out_dir, 'original')
            defaced_dir = os.path.join(patient_out_dir, 'defaced')
            os.makedirs(original_dir, exist_ok=True)
            os.makedirs(defaced_dir, exist_ok=True)
            
            modality_data = []
            nifti_to_deface = []
            
            # 시리즈별 처리
            for series_folder_name in sorted(os.listdir(patient_folder_path)):
                series_folder_path = os.path.join(patient_folder_path, series_folder_name)
                if not os.path.isdir(series_folder_path):
                    continue
                
                dcm_files = [f for f in os.listdir(series_folder_path) if f.lower().endswith('.dcm')]
                if not dcm_files:
                    continue
                
                print(f"\n  📁 시리즈: {series_folder_name}")
                
                first_dcm_path = os.path.join(series_folder_path, dcm_files[0])
                try:
                    dcm_meta = pydicom.dcmread(first_dcm_path, stop_before_pixels=True)
                    description = dcm_meta.get('SeriesDescription', 'UnknownDescription')
                except:
                    description = "ReadError"
                
                cleaned_desc = clean_filename(description)
                modality_data.append({
                    'subfolder_number': series_folder_name,
                    'series_description': description
                })
                print(f"    - Description: '{description}' → '{cleaned_desc}'")
                
                # 단일 DICOM (보고서)
                if len(dcm_files) == 1:
                    print(f"    - 📄 단일 DICOM 파일")
                    new_dcm_name = f"{patient_id}_{series_folder_name}_{cleaned_desc}.dcm"
                    shutil.copy2(first_dcm_path, os.path.join(original_dir, new_dcm_name))
                    print(f"    - ✅ 복사 완료: {new_dcm_name}")
                else:
                    # NIfTI 변환
                    new_nii_name = f"{patient_id}_{series_folder_name}_{cleaned_desc}.nii.gz"
                    dest_nii_path = os.path.join(original_dir, new_nii_name)
                    conversion_success = False
                    
                    try:
                        files_before = set(os.listdir(original_dir))
                        dicom2nifti.convert_directory(series_folder_path, original_dir, 
                                                     compression=True, reorient=True)
                        new_files = set(os.listdir(original_dir)) - files_before
                        
                        if not new_files:
                            raise dicom2nifti.exceptions.ConversionValidationError("No file created")
                        
                        os.rename(os.path.join(original_dir, new_files.pop()), dest_nii_path)
                        nifti_to_deface.append(dest_nii_path)
                        print(f"    - ✅ NIfTI 변환 완료: {new_nii_name}")
                        conversion_success = True
                    
                    except dicom2nifti.exceptions.ConversionValidationError as e:
                        print(f"    - ⚠️ 표준 변환 실패, 구조 모드 시도")
                        rescued_path = attempt_rescue_conversion(series_folder_path, original_dir)
                        
                        if rescued_path:
                            os.rename(rescued_path, dest_nii_path)
                            nifti_to_deface.append(dest_nii_path)
                            print(f"    - ✅ 구조 변환 성공: {new_nii_name}")
                            conversion_success = True
                    
                    if not conversion_success:
                        print(f"    - ⚠️ 변환 실패 (Localizer/Scout)")
                        new_folder_name = f"{patient_id}_{series_folder_name}_{cleaned_desc}"
                        shutil.copytree(series_folder_path, 
                                      os.path.join(original_dir, new_folder_name), 
                                      dirs_exist_ok=True)
                        print(f"    - ✅ 원본 DICOM 복사: {new_folder_name}")
            
            # Modality CSV 저장
            csv_path = os.path.join(original_dir, f"{patient_id}_modality.csv")
            pd.DataFrame(modality_data).to_csv(csv_path, index=False)
            print(f"\n  - 💾 CSV 저장: {os.path.basename(csv_path)}")
            
            # Defacing 실행
            if not nifti_to_deface:
                print("\n  - ✅ Deface할 NIfTI 없음")
                continue
            
            print(f"\n  - 🎭 Defacing 시작: {len(nifti_to_deface)}개 파일")
            
            for original_nii_path_gz in nifti_to_deface:
                nii_basename = os.path.basename(original_nii_path_gz)
                print(f"    - Refacing: {nii_basename}")
                
                temp_nii_path = None
                generated_refaced_path_nii = None
                
                try:
                    print("      -> 압축 해제...")
                    temp_nii_path = original_nii_path_gz.replace('.nii.gz', '.nii')
                    
                    with gzip.open(original_nii_path_gz, 'rb') as f_in, \
                         open(temp_nii_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                    
                    command = [executable_script_path, temp_nii_path, defaced_dir]
                    
                    image_type = get_image_type(nii_basename)
                    if image_type:
                        print(f"      -> 이미지 타입: {image_type}")
                        command.extend(['-imType', image_type])
                    
                    qc_flag = '1' if save_qc else '0'
                    command.extend(['-saveQCRenders', qc_flag])
                    
                    subprocess.run(command, check=True, capture_output=True, text=True)
                    
                    original_name_without_ext = nii_basename.replace('.nii.gz', '')
                    expected_output_name_nii = f"{original_name_without_ext}_deFaced.nii"
                    generated_refaced_path_nii = os.path.join(defaced_dir, expected_output_name_nii)
                    final_defaced_name_gz = f"{original_name_without_ext}_defaced.nii.gz"
                    final_defaced_path_gz = os.path.join(defaced_dir, final_defaced_name_gz)
                    
                    if os.path.exists(generated_refaced_path_nii):
                        print("      -> 압축 중...")
                        with open(generated_refaced_path_nii, 'rb') as f_in, \
                             gzip.open(final_defaced_path_gz, 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                        print(f"      -> ✅ 완료: {final_defaced_name_gz}")
                    else:
                        print(f"      -> ❌ 결과 파일 없음: {expected_output_name_nii}")
                
                except subprocess.CalledProcessError as e:
                    print(f"      -> ❌ Reface 실행 오류")
                    print(f"      -> STDOUT: {e.stdout}")
                    print(f"      -> STDERR: {e.stderr}")
                
                finally:
                    if temp_nii_path and os.path.exists(temp_nii_path):
                        os.remove(temp_nii_path)
                    if generated_refaced_path_nii and os.path.exists(generated_refaced_path_nii):
                        os.remove(generated_refaced_path_nii)
        
        except Exception as e:
            print(f"🚨 환자 '{patient_folder_name}' 처리 오류: {e}")
    
    if temp_reface_script_path and os.path.exists(temp_reface_script_path):
        os.remove(temp_reface_script_path)
    
    print("\n\n🎉 모든 처리 완료!")


# ============================================================
# 메인 실행
# ============================================================
if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="DICOM 전처리 + NIfTI 변환 + Defacing 통합 파이프라인"
    )
    parser.add_argument('--input_folder', type=str, required=True,
                       help='HP*/SA* 폴더가 있는 최상위 입력 경로')
    parser.add_argument('--output_folder', type=str, required=True,
                       help='최종 결과물 저장 경로')
    parser.add_argument('--reface_script_path', type=str, required=True,
                       help='run_mri_reface_docker.sh 전체 경로')
    parser.add_argument('--save_qc_renders', action='store_true',
                       help='QC 이미지 저장 여부')
    
    args = parser.parse_args()
    
    try:
        os.chmod(args.reface_script_path, 0o755)
    except:
        pass
    
    # STEP 1: DICOM 전처리
    input_path = Path(args.input_folder)
    preprocessed_path = preprocess_dicom_folders(input_path)
    
    # STEP 2: NIfTI 변환 + Defacing
    process_patient_data(
        str(preprocessed_path),
        args.output_folder,
        args.reface_script_path,
        args.save_qc_renders
    )