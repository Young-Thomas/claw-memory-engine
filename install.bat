@echo off
REM Claw Memory Engine 安装脚本 (Windows)
REM 适用于 Windows PowerShell/CMD

echo ========================================
echo   Claw Memory Engine 安装脚本
echo ========================================

REM 检查 Python 版本
echo.
echo 检查 Python 版本...
python --version
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

REM 创建虚拟环境
echo.
echo 创建虚拟环境...
python -m venv venv
if %errorlevel% neq 0 (
    echo [错误] 创建虚拟环境失败
    pause
    exit /b 1
)
echo [成功] 虚拟环境创建成功

REM 激活虚拟环境
echo.
echo 激活虚拟环境...
call venv\Scripts\activate.bat

REM 安装依赖
echo.
echo 安装依赖...
python -m pip install --upgrade pip
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [错误] 安装依赖失败
    pause
    exit /b 1
)
echo [成功] 依赖安装成功

REM 安装为命令行工具
echo.
echo 安装为命令行工具...
pip install -e .
if %errorlevel% neq 0 (
    echo [错误] 安装命令行工具失败
    pause
    exit /b 1
)
echo [成功] 命令行工具安装成功

REM 验证安装
echo.
echo 验证安装...
claw --version
claw --help

REM 完成
echo.
echo ========================================
echo   安装完成！
echo ========================================
echo.
echo 使用方法:
echo   1. 激活虚拟环境：venv\Scripts\activate
echo   2. 运行命令：claw --help
echo   3. 记录命令：claw remember ^<别名^> ^<命令^>
echo.

pause
