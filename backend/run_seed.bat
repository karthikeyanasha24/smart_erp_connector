@echo off
echo.
echo ==========================================
echo  SmarterP - Seeding RBAC Users
echo ==========================================
echo.
cd /d %~dp0
python scripts/seed_all_users.py
echo.
pause
