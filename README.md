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

## 폰트

`assets/fonts/Gaegu-Bold.ttf`: SIL Open Font License 1.1 (`assets/fonts/OFL.txt`)
