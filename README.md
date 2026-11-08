# kids-autoedit

대본 한 줄과 이미지 한 장으로 세로형(1080x1920) 응원 영상을 자동으로 만드는 워크플로입니다.

```
대본 검수 → TTS 음성 합성 → 무음 트리밍·-14.9 LUFS 정규화 → FFmpeg 1080x1920 30fps 자막·장면 합성 → Whisper 받아쓰기 대조 검수
```

## 결과

- 결과 영상: [`output/twin_cheer.mp4`](output/twin_cheer.mp4) (1080x1920, 30fps, 6.84초)
- 검수 리포트: [`output/report.json`](output/report.json)
- 자막: [`output/subs.ass`](output/subs.ass)

| 항목 | 결과 | 기준 |
|---|---|---|
| 해상도 | 1080x1920 | 1080x1920 |
| 프레임레이트 | 30 fps | 30 fps |
| 통합 음량 | -15.0 LUFS | -14.9 ±0.5 |
| 트루 피크 | -1.4 dBFS | -1.5 기준 |
| Whisper 글자 오차율(CER) | 0.0 % | 5 % 이하 |

## 단계

1. **대본 검수**: 맞춤법·띄어쓰기 교정, 문장부호 추가, 자막 단위로 분할
   - 원문: `안녕 반가워 열심히 하고 있구나 잘 할수 있어 화이팅!`
   - 교정: `안녕! 반가워! / 열심히 하고 있구나. / 잘할 수 있어. / 화이팅!`
2. **TTS**: 문장마다 Google TTS(한국어)로 합성, 1.12배속. 문장 길이가 자막 타이밍이 됩니다.
3. **트리밍·정규화**: 앞뒤 무음 제거(-45dB), 0.3초 간격으로 연결, 2-pass `loudnorm`으로 -14.9 LUFS. 피크 한도 때문에 모자란 음량은 게인 보정과 리미터로 맞춥니다.
4. **합성**: 흐린 배경 위에 이미지를 천천히 확대(6%)하며 배치하고, Gaegu 손글씨체 자막을 문장 타이밍에 맞춰 넣습니다. H.264 + AAC.
5. **대조 검수**: 완성 영상을 faster-whisper(medium)로 다시 받아써서 대본과 글자 단위로 비교하고, 해상도·fps·음량과 함께 합격 여부를 `report.json`에 기록합니다.

## 실행

필요한 것: Python 3.10+, FFmpeg (libass 포함)

```bash
pip install -r requirements.txt
python pipeline.py
```

- 장면 이미지는 `input/scene.webp`, 대본은 `pipeline.py`의 `LINES`에서 바꿉니다.
- 중간 파일은 `build/`, 결과는 `output/`에 생깁니다.
- API 키가 필요 없습니다.

## 완성 영상을 구글 드라이브로 자동 업로드

편집이 끝나면 영상을 드라이브에 올리는 6단계가 이어집니다. 방법은 두 가지이고, 둘 다 쓰면 둘 다 실행됩니다. 업로드 결과는 `output/report.json`의 `upload`에 남습니다.

### A. 데스크톱용 Drive 동기화 폴더 (설정이 가장 쉬움)

서버 PC에 [데스크톱용 Google Drive](https://www.google.com/drive/download/)가 로그인돼 있으면, 동기화 폴더에 복사하는 것만으로 업로드됩니다.

```bash
python pipeline.py --upload-dir "G:\내 드라이브\OUP PUT" --name "twinroozi_과제.mp4"
```

- 공유 링크는 드라이브에서 직접 만들거나, `OUP PUT` 폴더를 한 번만 "링크가 있는 모든 사용자"로 공유해 두면 됩니다.
- Drive 앱이 켜져 있어야 실제로 올라갑니다. 서버 PC가 로그인할 때 Drive가 자동 실행되도록 설정하세요.

### B. rclone으로 바로 업로드 + 공유 링크 자동 생성 (서버용 추천)

Drive 앱 없이 명령줄에서 바로 올리고, "링크가 있는 모든 사용자(뷰어)" 링크까지 만들어 `report.json`에 적습니다.

1. 설치: `winget install Rclone.Rclone`
2. 드라이브 연결(한 번만): `rclone config` → `n`(새 원격) → 이름 `gdrive` → 저장소 `drive` → client_id/secret은 빈칸 → scope `1`(전체 접근) → 나머지 기본값 → 브라우저에서 구글 계정 로그인·허용
3. 확인: `rclone lsd gdrive:` 에 내 드라이브 폴더 목록이 나오면 성공
4. 실행:

```bash
python pipeline.py --rclone "gdrive:OUP PUT" --name "twinroozi_과제.mp4"
```

매번 옵션을 쓰기 싫으면 환경변수로 정해 둡니다(`UPLOAD_DIR`, `RCLONE_DEST`).

```bash
setx RCLONE_DEST "gdrive:OUP PUT"
```

- rclone 로그인 정보는 `%APPDATA%\rclone\rclone.conf`에 저장됩니다. 이 파일은 저장소나 드라이브에 올리지 마세요.

## 폰트

`assets/fonts/Gaegu-Bold.ttf`: SIL Open Font License 1.1 (`assets/fonts/OFL.txt`)
