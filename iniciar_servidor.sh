#!/bin/zsh
cd "$(dirname "$0")"
echo "======================================================================"
echo " Iniciando Plataforma de Duvidas de Investigacao Operacional (FE-UEM)"
echo "======================================================================"
./.venv/bin/python app.py
