#!/bin/bash
# One-time 1688 login for automated sourcing. Double-click to run.
cd "$(dirname "$0")"
if [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
fi
export API_SERVER_URL=https://project-user-dashboard-api.vercel.app
python scripts/login_1688.py
echo ""
read -p "끝났습니다. 이 창은 닫아도 됩니다. (Enter 키를 누르세요)" _
