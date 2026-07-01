#!/bin/bash
dir_path=$(dirname "$(readlink -f "$0")")

pip install pyinstaller
python -m PyInstaller --onefile "$dir_path/fgwsz-package.py" \
    --distpath "$dir_path/build/linux/dist" \
    --workpath "$dir_path/build/linux/work" \
    --specpath "$dir_path/build/linux/spec" \
    --clean
