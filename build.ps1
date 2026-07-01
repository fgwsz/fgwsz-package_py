$dir_path=Split-Path -Parent $MyInvocation.MyCommand.Definition

pip install pyinstaller
python -m PyInstaller --onefile "$dir_path/fgwsz-package.py" `
    --distpath "$dir_path/build/windows/dist" `
    --workpath "$dir_path/build/windows/work" `
    --specpath "$dir_path/build/windows/spec" `
    --clean
