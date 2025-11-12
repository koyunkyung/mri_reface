#### 목차

- [사전 준비사항](#사전-준비사항)
- [실행 방법](#실행-방법)
- [결과물 및 폴더 구조](#결과물-및-폴더-구조)

---


### ☝🏻 사전 준비사항

### 1단계: Python 패키지 설치

#### Windows 사용자

명령 프롬프트 또는 PowerShell에서 실행:
```cmd
pip install pydicom dicom2nifti pandas numpy
```

<details>
<summary><b>Mac/Linux 사용자</b></summary>
```bash
pip3 install pydicom dicom2nifti pandas numpy
```

</details>

### 3단계: Docker 설치 및 실행

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
   - **Apple Silicon (M1/M2/M3)**: "Mac with Apple silicon"
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
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

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

### 4단계: MRI Reface Docker 이미지 다운로드

Docker가 실행 중인 상태에서 다음 명령어를 실행합니다:
```cmd
docker pull poldracklab/pydeface
```

> 📌 **참고**: 약 500MB~1GB 다운로드가 필요하며, 인터넷 속도에 따라 몇 분 소요됩니다.



### ✌🏻 실행 방법





### 👌🏻 결과물 및 폴더 구조