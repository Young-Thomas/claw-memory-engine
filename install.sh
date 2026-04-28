#!/bin/bash
# Claw Memory Engine 安装脚本
# 适用于 Linux/macOS

set -e

echo "🧠 Claw Memory Engine 安装脚本"
echo "================================"

# 检查 Python 版本
echo ""
echo "检查 Python 版本..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "检测到 Python $python_version"

# 创建虚拟环境
echo ""
echo "创建虚拟环境..."
python3 -m venv venv
echo "✅ 虚拟环境创建成功"

# 激活虚拟环境
echo ""
echo "激活虚拟环境..."
source venv/bin/activate

# 安装依赖
echo ""
echo "安装依赖..."
pip install --upgrade pip
pip install -r requirements.txt
echo "✅ 依赖安装成功"

# 安装为命令行工具
echo ""
echo "安装为命令行工具..."
pip install -e .
echo "✅ 命令行工具安装成功"

# 验证安装
echo ""
echo "验证安装..."
claw --version
claw --help

# 完成
echo ""
echo "================================"
echo "✅ 安装完成！"
echo ""
echo "使用方法:"
echo "  1. 激活虚拟环境：source venv/bin/activate"
echo "  2. 运行命令：claw --help"
echo "  3. 记录命令：claw remember <别名> <命令>"
echo ""
