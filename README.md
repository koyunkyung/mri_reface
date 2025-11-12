- [사전 준비사항](#사전-준비사항)
- [실행 방법](#실행-방법)
- [결과물 및 폴더 구조](#결과물-및-폴더-구조)
- [문제 해결](#문제-해결)

---


### ☝🏻 사전 준비사항

#### 1단계: Python 패키지 및 VSCode Extension 설치

NIfTI 파일 변환 결과를 직접 확인하고 싶다면:
1. **VSCode 열기**
2. 왼쪽 사이드바에서 **Extensions** 아이콘 클릭 (또는 `Ctrl+Shift+X`)
3. 검색창에 **"NiiVue"** 입력
4. **NiiVue** (by Korbinian Eckstein) 설치
5. 설치 후 `.nii` 또는 `.nii.gz` 파일을 클릭하면 뇌 영상을 3D로 바로 확인 가능
> 💡 **팁**: NiiVue를 설치하면 변환된 NIfTI 파일을 별도 프로그램 없이 VSCode에서 바로 시각화할 수 있습니다!

#### Windows 사용자

명령 프롬프트 또는 PowerShell에서 실행 
(VSCode에서 실행 중이라면 상단 탭에서 'Terminal' 탭을 클릭하고 'New Terminal'을 다시 클릭하면 뜨는 창에서 실행하시면 됩니다):

```cmd
pip install pydicom dicom2nifti pandas numpy
```

<details>
<summary><b>Mac/Linux 사용자</b></summary>

```bash
pip3 install pydicom dicom2nifti pandas numpy
```

</details>

#### 2단계: Docker 설치 및 실행

#### Windows 사용자

1. [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/) 다운로드
2. 설치 파일(`Docker Desktop Installer.exe`) 실행
3. 설치 완료 후 **컴퓨터 재시작**
4. Docker Desktop 실행 (시작 메뉴에서 검색)
5. 시스템 트레이에 고래 아이콘이 나타나면 성공

**설치 확인:**
```cmd
docker --version
```

<details>
<summary><b>Mac 사용자</b></summary>

1. [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/) 다운로드
2. Mac 칩 종류에 맞는 버전 선택:
   - **Apple Silicon (M1/M2/M3/M4)**: "Mac with Apple silicon"
   - **Intel 칩**: "Mac with Intel chip"
3. `Docker.dmg` 파일 실행
4. Docker 아이콘을 Applications 폴더로 드래그
5. Applications에서 Docker 실행

**설치 확인:**
```bash
docker --version
```

</details>

<details>
<summary><b>Linux 사용자 (Ubuntu/Debian 기준)</b></summary>

```bash
# 시스템 패키지 업데이트
sudo apt-get update

# 필요한 패키지 설치
sudo apt-get install -y ca-certificates curl gnupg lsb-release

# Docker의 공식 GPG 키 추가
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Docker 저장소 설정
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null"

# Docker 설치
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io

# Docker 서비스 시작
sudo systemctl start docker
sudo systemctl enable docker

# 현재 사용자를 docker 그룹에 추가
sudo usermod -aG docker $USER
```

**설치 확인:**

```bash
docker --version
```

</details>

---

#### 3단계: MRI Reface Docker 다운로드 및 설정 가이드

#### 3-1단계: Docker가 실행 중인 상태에서 다음 명령어를 실행합니다

```cmd
docker pull poldracklab/pydeface
```

> 📌 **참고**: 약 500MB~1GB 다운로드가 필요하며, 인터넷 속도에 따라 몇 분 소요됩니다.

#### 3-2단계:

#### Windows 사용자

[NITRC MRI Reface 페이지](https://www.nitrc.org/frs/?group_id=1525) → 최신 릴리즈의 mri_reface_docker.tar.gz 다운로드

7-Zip으로 tar.gz → tar 순서로 풀기 → 예: 

```cmd
C:\Users\YourName\Documents\mri_reface_docker\
```

폴더 내용 예시
```
mri_reface_docker/
├─ mri_reface_docker_image
└─ run_mri_reface_docker.sh   ← 중요
```

<details>
<summary><b>Mac 사용자</b></summary>

```bash
cd ~/Downloads
tar -xzf mri_reface_docker.tar.gz
mv mri_reface_docker ~/Documents/
ls -la ~/Documents/mri_reface_docker
```
</details>

<details>
<summary><b>Linux 사용자 (Ubuntu/Debian 기준)</b></summary>

```bash
cd ~/Downloads
# URL은 NITRC 페이지에서 복사
wget https://www.nitrc.org/frs/download.php/xxxxx/mri_reface_docker.tar.gz
tar -xzf mri_reface_docker.tar.gz
mv mri_reface_docker ~/project/
ls -la ~/project/mri_reface_docker
```

</details>

Docker 이미지 로드
#### Windows (PowerShell/명령프롬프트)
```cmd
cd C:\Users\YourName\Documents\mri_reface_docker
docker load -i mri_reface_docker_image
docker images
```

<details>
<summary><b>Mac/Linux 사용자</b></summary>

```bash
cd ~/Documents/mri_reface_docker   # 또는 본인 경로
docker load -i mri_reface_docker_image
docker images
```

</details>

### ✌🏻 실행 방법

#### Windows 사용자

1. **명령 프롬프트** 또는 **PowerShell**을 열기
2. 스크립트가 있는 폴더로 이동:

```cmd
   cd C:\Users\YourName\Documents\project
```

3. 다음 명령어 실행 (경로는 실제 환경에 맞게 수정):

```cmd
python dcm_nii_reface.py ^
    --input_folder "C:\Users\YourName\Documents\raw" ^
    --output_folder "C:\Users\YourName\Documents\deface_results" ^
    --reface_script_path "C:\Users\YourName\Documents\scripts\run_mri_reface_docker.sh" ^
    --save_qc_renders
```


<details>
<summary><b>Mac 사용자</b></summary>

1. **터미널** 열기
2. 스크립트가 있는 폴더로 이동:
```bash
   cd ~/Documents/project
```

3. **중요**: 스크립트에 실행 권한 부여:
```bash
   chmod +x /path/to/run_mri_reface_docker.sh
```

4. 다음 명령어 실행:
```bash
python3 dcm_nii_reface.py \
    --input_folder ~/Documents/raw \
    --output_folder ~/Documents/deface_results \
    --reface_script_path ~/Desktop/scripts/run_mri_reface_docker.sh \
    --save_qc_renders
```

</details>

<details>
<summary><b>Linux 사용자</b></summary>

1. 터미널 열기
2. 스크립트가 있는 폴더로 이동:

```bash
   cd ~/project
```

3. 실행 권한 부여:

```bash
   chmod +x /path/to/run_mri_reface_docker.sh
```

4. 명령어 실행:

```bash
python3 dcm_nii_reface.py \
    --input_folder /home/username/raw \
    --output_folder /home/username/deface_results \
    --reface_script_path /home/username/scripts/run_mri_reface_docker.sh \
    --save_qc_renders
```

</details>

---

#### 📝 명령어 옵션 설명

| 옵션 | 필수 여부 | 설명 |
|------|----------|------|
| `--input_folder` | ✅ 필수 | HP*/SA* 폴더가 있는 입력 경로 |
| `--output_folder` | ✅ 필수 | 처리 결과를 저장할 폴더 |
| `--reface_script_path` | ✅ 필수 | Docker 실행 스크립트의 전체 경로 |
| `--save_qc_renders` | ❌ 선택 | QC 이미지 저장 (플래그만 추가) |

---


### 👌🏻 결과물 및 폴더 구조

프로그램이 성공적으로 실행되면 다음과 같은 구조로 결과물이 생성됩니다:
```
deface_results/
├── PatientID_001/
│   ├── original/                          # 원본 파일
│   │   ├── PatientID_001_1_T1_MPRAGE.nii.gz
│   │   ├── PatientID_001_2_T2_FLAIR.nii.gz
│   │   └── PatientID_001_modality.csv      # 메타데이터
│   └── defaced/                           # 익명화된 파일
│       ├── PatientID_001_1_T1_MPRAGE_defaced.nii.gz
│       └── PatientID_001_2_T2_FLAIR_defaced.nii.gz
├── PatientID_002/
│   ├── original/
│   └── defaced/
└── ...
```


### 🤯 문제 해결

#### ❌ "docker: command not found" 오류

**원인**: Docker가 설치되지 않았거나 실행 중이지 않음

**해결 방법**:
- Docker Desktop이 실행 중인지 확인
- 컴퓨터 재시작 후 다시 시도
- Docker 재설치

---

#### ❌ "Permission denied" 오류

**원인**: 스크립트 파일에 실행 권한이 없음 (Mac/Linux)

**해결 방법**:
```bash
chmod +x /path/to/run_mri_reface_docker.sh
```

---

#### ❌ "ModuleNotFoundError" 오류

**원인**: 필요한 Python 패키지가 설치되지 않음

**해결 방법**:
```cmd
# Windows
pip install pydicom dicom2nifti pandas numpy

# Mac/Linux
pip3 install pydicom dicom2nifti pandas numpy
```

---

#### ❌ Docker 이미지 다운로드 실패

**원인**: 인터넷 연결 문제 또는 Docker Hub 접근 제한

**해결 방법**:
- 인터넷 연결 확인
- VPN 사용 중이라면 일시적으로 비활성화
- Docker Desktop 재시작 후 다시 시도



