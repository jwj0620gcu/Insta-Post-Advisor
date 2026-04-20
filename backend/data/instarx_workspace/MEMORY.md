# NoteRx 로컬 메모리(MEMORY)

이 파일은 **장기 설명 영역**이다. 일별 진단 로그는 `memory/YYYY-MM-DD.md`, 전체 JSON은 `memory/records/`에 저장된다.

## 용도

- 사람이 읽기 쉬움: `grep`, 에디터, 버전관리(git 포함)에 바로 활용 가능
- 원본 데이터는 `memory/records/<id>.json` + SQLite `diagnosis_history`에 이중 기록되어 조회/백업/복구가 쉽다

## 참고

- 이력 삭제 시 `records`의 JSON도 함께 삭제되며, 일별 md에는 삭제 흔적 라인이 남아 감사 추적이 가능하다.
