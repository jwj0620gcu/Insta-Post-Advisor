#!/bin/bash
# NoteRx 원클릭 시작 스크립트
# Usage: ./start.sh

set -e

echo "💊 NoteRx 시작 중..."

# Check .env
if [ ! -f backend/.env ] && [ ! -f .env ]; then
  echo "⚠️  .env 파일을 찾을 수 없습니다. .env.example을 복사하고 API Key를 입력하세요"
  echo "   cp .env.example backend/.env"
fi

# Start backend
echo "🔧 백엔드 서비스 시작 중..."
cd backend
source venv/bin/activate 2>/dev/null || python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt -q
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
cd ..

# Start frontend
echo "🎨 프론트엔드 서비스 시작 중..."
cd frontend
npm install -q 2>/dev/null
npx vite --port 5173 &
FRONTEND_PID=$!
cd ..

echo ""
echo "✅ NoteRx가 시작되었습니다!"
echo "   프론트엔드: http://localhost:5173"
echo "   백엔드: http://localhost:8000"
echo "   API 문서: http://localhost:8000/docs"
echo ""
echo "Ctrl+C를 눌러 모든 서비스를 중지하세요"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
