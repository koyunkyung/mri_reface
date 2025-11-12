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

logging.getLogger('dicom2nifti').setLevel(logging.CRITICAL)

def clean_filename(text):
    if not text: return "UnknownDescription"
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
    """
    슬라이스 간격이 불일치하는 시리즈에서 가장 긴 연속 부분을 찾아 변환을 시도합니다.
    """
    print("      -> 🧠 구조 모드 발동: 가장 긴 연속 슬라이스 블록을 찾습니다...")
    dicom_slices = []
    for filename in os.listdir(series_folder_path):
        filepath = os.path.join(series_folder_path, filename)
        if not filepath.lower().endswith('.dcm'): continue
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
        print("      -> ❌ 구조 실패: 유효한 슬라이스가 너무 적습니다.")
        return None

    # Z축 위치를 기준으로 슬라이스 정렬
    dicom_slices.sort(key=lambda s: s['pos'][2])
    
    # 슬라이스 간격 계산
    increments = [np.linalg.norm(np.array(dicom_slices[i+1]['pos']) - np.array(dicom_slices[i]['pos'])) for i in range(len(dicom_slices)-1)]

    # 가장 긴 연속 그룹 찾기
    if not increments: return None
    
    longest_group = []
    current_group = [dicom_slices[0]]
    for i in range(len(increments)):
        # 부동소수점 오차를 고려하여 비교
        if np.isclose(increments[i], increments[i-1] if i > 0 else increments[i]):
            current_group.append(dicom_slices[i+1])
        else:
            if len(current_group) > len(longest_group):
                longest_group = current_group
            current_group = [dicom_slices[i+1]]
    if len(current_group) > len(longest_group):
        longest_group = current_group

    if len(longest_group) < 5:
        print("      -> ❌ 구조 실패: 일관된 슬라이스 그룹이 너무 짧습니다.")
        return None
        
    print(f"      -> ✅ 가장 긴 그룹({len(longest_group)}개 슬라이스)을 찾았습니다. 변환을 재시도합니다.")
    try:
        dicom_objects = [pydicom.dcmread(s['path']) for s in longest_group]
        temp_nii_path = os.path.join(temp_output_dir, "rescued_temp.nii.gz")
        convert_dicom.dicom_array_to_nifti(dicom_objects, temp_nii_path, reorient=True)
        return temp_nii_path
    except Exception as e:
        print(f"      -> ❌ 구조 변환 실패: {e}")
        return None

def process_patient_data(input_root, output_root, reface_script_path, save_qc):
    # ... (스크립트 상단은 이전과 동일) ...
    print("🚀 MRI 처리 파이프라인 시작...")
    if not os.path.isfile(reface_script_path):
        print(f"🚨 치명적 오류: --reface_script_path가 파일이 아닙니다! '{reface_script_path}'")
        return
    temp_reface_script_path = None
    executable_script_path = reface_script_path
    try:
        with open(reface_script_path, 'r') as f: script_content = f.read()
        platform_flag = "--platform linux/amd64"
        if platform_flag not in script_content:
            print("  - 🔧 Apple Silicon 환경 감지, 호환성 패치 적용...")
            target_line = "docker run --rm -ti --mount"
            replacement_line = f"docker run --rm -ti {platform_flag} --mount"
            script_content = script_content.replace(target_line, replacement_line)
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.sh') as temp_script:
                temp_script.write(script_content)
                temp_reface_script_path = temp_script.name
            os.chmod(temp_reface_script_path, 0o755)
            executable_script_path = temp_reface_script_path
    except Exception as patch_e:
        print(f"  - ⚠️ 자동 패치 오류: {patch_e}. 원본 스크립트로 진행.")
    
    for patient_folder_name in os.listdir(input_root):
        patient_folder_path = os.path.join(input_root, patient_folder_name)
        if not os.path.isdir(patient_folder_path): continue
        try:
            patient_id = patient_folder_name.split('_')[0]
            print(f"\n========================================\n🧠 환자 ID 처리 중: {patient_id}\n========================================")
            patient_out_dir = os.path.join(output_root, patient_id)
            original_dir = os.path.join(patient_out_dir, 'original')
            defaced_dir = os.path.join(patient_out_dir, 'defaced')
            os.makedirs(original_dir, exist_ok=True)
            os.makedirs(defaced_dir, exist_ok=True)
            print(f"  - 출력 폴더 생성: {patient_out_dir}")
            modality_data = []
            nifti_to_deface = []
            for series_folder_name in sorted(os.listdir(patient_folder_path)):
                series_folder_path = os.path.join(patient_folder_path, series_folder_name)
                if not os.path.isdir(series_folder_path): continue
                dcm_files = [f for f in os.listdir(series_folder_path) if f.lower().endswith('.dcm')]
                if not dcm_files: continue
                print(f"\n  📁 시리즈 '{series_folder_name}' 처리 중...")
                first_dcm_path = os.path.join(series_folder_path, dcm_files[0])
                try:
                    dcm_meta = pydicom.dcmread(first_dcm_path, stop_before_pixels=True)
                    description = dcm_meta.get('SeriesDescription', 'UnknownDescription')
                except: description = "ReadError"
                cleaned_desc = clean_filename(description)
                modality_data.append({'subfolder_number': series_folder_name, 'series_description': description})
                print(f"    - Description: '{description}' -> '{cleaned_desc}'")

                if len(dcm_files) == 1:
                    print(f"    - 📄 단일 DICOM 파일(보고서)로 간주합니다.")
                    new_dcm_name = f"{patient_id}_{series_folder_name}_{cleaned_desc}.dcm"
                    shutil.copy2(first_dcm_path, os.path.join(original_dir, new_dcm_name))
                    print(f"    - ✅ 단일 DICOM 파일 복사 완료: {new_dcm_name}")
                else:
                    new_nii_name = f"{patient_id}_{series_folder_name}_{cleaned_desc}.nii.gz"
                    dest_nii_path = os.path.join(original_dir, new_nii_name)
                    conversion_success = False
                    try:
                        files_before = set(os.listdir(original_dir))
                        dicom2nifti.convert_directory(series_folder_path, original_dir, compression=True, reorient=True)
                        new_files = set(os.listdir(original_dir)) - files_before
                        if not new_files: raise dicom2nifti.exceptions.ConversionValidationError("No file created")
                        os.rename(os.path.join(original_dir, new_files.pop()), dest_nii_path)
                        nifti_to_deface.append(dest_nii_path)
                        print(f"    - ✅ NIfTI 변환 및 이름 변경 완료: {new_nii_name}")
                        conversion_success = True
                    except dicom2nifti.exceptions.ConversionValidationError as e:
                        print(f"    - ⚠️ 표준 변환 실패 ({e}), 구조 모드를 시도합니다.")
                        rescued_path = attempt_rescue_conversion(series_folder_path, original_dir)
                        if rescued_path:
                            os.rename(rescued_path, dest_nii_path)
                            nifti_to_deface.append(dest_nii_path)
                            print(f"    - ✅ 구조 변환 성공: {new_nii_name}")
                            conversion_success = True
                    
                    if not conversion_success:
                        print(f"    - ⚠️ 최종 변환 실패 (Localizer/Scout).")
                        new_folder_name = f"{patient_id}_{series_folder_name}_{cleaned_desc}"
                        shutil.copytree(series_folder_path, os.path.join(original_dir, new_folder_name), dirs_exist_ok=True)
                        print(f"    - ✅ 원본 DICOM 폴더 복사 완료: {new_folder_name}")

            # ... (스크립트 하단 Reface 로직은 이전과 동일) ...
            csv_path = os.path.join(original_dir, f"{patient_id}_modality.csv")
            pd.DataFrame(modality_data).to_csv(csv_path, index=False)
            print(f"\n  - 💾 Modality 정보 저장 완료: {os.path.basename(csv_path)}")
            if not nifti_to_deface:
                print("\n  - ✅ Deface할 NIfTI 파일이 없습니다. 다음으로 넘어갑니다.")
                continue
            print(f"\n  - 🎭 총 {len(nifti_to_deface)}개의 NIfTI 파일에 대해 Reface 시작...")
            for original_nii_path_gz in nifti_to_deface:
                nii_basename = os.path.basename(original_nii_path_gz)
                print(f"    - Refacing: {nii_basename}")
                temp_nii_path = None
                generated_refaced_path_nii = None
                try:
                    print("      -> .nii.gz 압축 해제 중...")
                    temp_nii_path = original_nii_path_gz.replace('.nii.gz', '.nii')
                    with gzip.open(original_nii_path_gz, 'rb') as f_in, open(temp_nii_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                    command = [executable_script_path, temp_nii_path, defaced_dir]
                    image_type = get_image_type(nii_basename)
                    if image_type:
                        print(f"      -> 이미지 타입 자동 감지: {image_type}")
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
                        print("      -> 결과 파일 압축 중...")
                        with open(generated_refaced_path_nii, 'rb') as f_in, gzip.open(final_defaced_path_gz, 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                        print(f"      -> ✅ Reface 완료 및 저장: {final_defaced_name_gz}")
                    else:
                        print(f"      -> ❌ Reface 결과(.nii) 파일을 찾을 수 없습니다: {expected_output_name_nii}")
                except subprocess.CalledProcessError as e:
                    print(f"      -> ❌ Reface 스크립트 실행 오류:")
                    print(f"      -> [STDOUT]:\n{e.stdout}")
                    print(f"      -> [STDERR]:\n{e.stderr}")
                finally:
                    if temp_nii_path and os.path.exists(temp_nii_path): os.remove(temp_nii_path)
                    if generated_refaced_path_nii and os.path.exists(generated_refaced_path_nii): os.remove(generated_refaced_path_nii)
        except Exception as e:
            print(f"🚨 환자 '{patient_folder_name}' 처리 중 심각한 오류 발생: {e}")
    if temp_reface_script_path and os.path.exists(temp_reface_script_path):
        os.remove(temp_reface_script_path)
    print("\n\n🎉 모든 환자 데이터 처리 완료!")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="MRI DICOM to Defaced NIfTI Conversion Pipeline.")
    parser.add_argument('--input_folder', type=str, required=True, help='최상위 입력 폴더 경로.')
    parser.add_argument('--output_folder', type=str, required=True, help='최종 결과물이 저장될 최상위 출력 폴더 경로.')
    parser.add_argument('--reface_script_path', type=str, required=True, help="'run_mri_reface_docker.sh' 스크립트 파일의 전체 경로.")
    parser.add_argument('--save_qc_renders', action='store_true', help="이 플래그를 추가하면 QC용 .png 이미지들을 함께 저장합니다.")
    args = parser.parse_args()
    
    try: os.chmod(args.reface_script_path, 0o755)
    except: pass
        
    process_patient_data(args.input_folder, args.output_folder, args.reface_script_path, args.save_qc_renders)

