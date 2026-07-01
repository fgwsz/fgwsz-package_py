# fgwsz-package

一个轻量级文件打包/解包工具，使用单字节 XOR 进行混淆，专为网络传输和简单数据保护而设计。

---

## ✨ 特性

- **简单高效**：将多个文件/目录打包为单个 `.fgwsz` 包，支持 **列表查看**、**解包还原**。
- **混淆保护**：每个文件使用独立的随机密钥进行 **XOR 混淆**，防止直接查看包结构。
- **跨平台兼容**：纯 Python 实现，仅依赖标准库，可在 Windows / Linux / macOS 上运行。
- **与 C++ 版本二进制兼容**：与同名 C++ 工具生成的包可互相读写，便于多语言协作。
- **网络序存储**：长度字段使用 **大端序**，确保跨平台网络传输时解析一致。
- **跨平台构建**：提供 Windows（`build.ps1`）和 Linux（`build.sh`）打包脚本，一键生成独立可执行文件。
- **符号链接处理**：打包时自动跳过所有符号链接，避免循环引用和内容重复。

---

## 📦 安装

### 方式一：直接使用 Python 脚本

```bash
# 克隆仓库
git clone https://github.com/your-repo/fgwsz-package.git
cd fgwsz-package

# 直接运行
python fgwsz-package.py -h
```

### 方式二：使用预构建的可执行文件

从 Releases 页面下载对应平台的可执行文件：

- **Windows**: `fgwsz-package.exe`
- **Linux**: `fgwsz-package`
- **macOS**: `fgwsz-package`

### 方式三：自行构建

```bash
# Windows (PowerShell)
.\build.ps1

# Linux / macOS (Bash)
chmod +x build.sh
./build.sh
```

构建产物位于：
- Windows: `build/windows/dist/fgwsz-package.exe`
- Linux: `build/linux/dist/fgwsz-package`

---

## 🚀 使用方法

```text
Usages:
    Pack  : -c <output-package-path> <input-path-1> [<input-path-2> ...]
    Unpack: -x <input-package-path> <output-directory-path>
    List  : -l <input-package-path>
```

### 📋 示例

```bash
# 打包单个文件（解包时文件直接放入输出根目录）
fgwsz-package -c out.fgwsz README.md

# 打包目录（保留目录结构）
fgwsz-package -c out.fgwsz source/

# 混合打包文件与目录
fgwsz-package -c out.fgwsz README.md source/ doc/guide.txt

# 解包到 output 目录
fgwsz-package -x out.fgwsz output

# 查看包内文件列表
fgwsz-package -l out.fgwsz
```

### 📁 打包行为说明

| 输入类型 | 包内存储路径 | 解包位置（以 `out` 为例） |
|----------|--------------|---------------------------|
| 文件 `a.txt` | `a.txt` | `out/a.txt` |
| 目录 `source/` | `source/...` | `out/source/...` |
| 文件 `subdir/file.txt` | `file.txt`（**忽略目录层级**） | `out/file.txt` |

#### 目录处理细节
- 打包目录时，**始终包含目录自身**，即解包后会在输出目录下创建该目录。
- 所有符号链接（软链接）在打包时被**自动跳过**，不会打包链接本身，也不会跟随链接。
- 目录遍历**不跟随符号链接**，避免循环引用。

---

## 📦 包格式（二进制结构）

每个文件条目存储为：

```text
[KEY (1 byte)]          # 随机密钥（1~255），明文存储
[PATH_LEN (8 bytes)]    # 路径长度，大端序，使用 KEY 异或混淆
[PATH (N bytes)]        # 路径字符串（UTF-8），使用 KEY 异或混淆
[CONTENT_LEN (8 bytes)] # 文件内容长度，大端序，使用 KEY 异或混淆
[CONTENT (M bytes)]     # 文件原始二进制内容，使用 KEY 异或混淆
```

- **长度字段**均使用 **大端序**（网络字节序），确保跨平台兼容。
- **混淆**：每个条目使用独立的随机密钥对长度和数据进行单字节 XOR。
- **混淆仅提供轻微防护**，不保证强加密，请勿用于安全敏感场景。

---

## 🏗️ 项目结构

```text
fgwsz-package/
├── fgwsz-package.py          # 主脚本
├── build.ps1                 # Windows 构建脚本 (PowerShell)
├── build.sh                  # Linux/macOS 构建脚本 (Bash)
├── .gitignore                # Git 忽略规则
├── LICENSE                   # MIT 许可证
└── build/                    # 构建产物目录
    ├── windows/
    │   ├── dist/             # Windows 可执行文件输出
    │   ├── work/             # 临时构建文件
    │   └── spec/             # PyInstaller spec 文件
    └── linux/
        ├── dist/             # Linux 可执行文件输出
        ├── work/             # 临时构建文件
        └── spec/             # PyInstaller spec 文件
```

---

## 🛠️ 构建说明

### Windows (PowerShell)

```powershell
.\build.ps1
```

脚本自动：
1. 安装 PyInstaller
2. 执行打包，生成 `build/windows/dist/fgwsz-package.exe`

### Linux / macOS (Bash)

```bash
chmod +x build.sh
./build.sh
```

脚本自动：
1. 安装 PyInstaller
2. 执行打包，生成 `build/linux/dist/fgwsz-package`

### 手动构建

```bash
# 安装 PyInstaller
pip install pyinstaller

# 单文件打包（默认输出到 ./dist）
pyinstaller --onefile fgwsz-package.py

# 自定义输出路径
pyinstaller --onefile fgwsz-package.py \
    --distpath ./build/dist \
    --workpath ./build/work \
    --specpath ./build/spec
```

---

## 💻 开发与测试

### 手动测试

```bash
# 准备测试文件
echo "hello" > a.txt
mkdir -p subdir
echo "world" > subdir/b.txt
mkdir source
echo "cpp" > source/main.cpp

# 打包混合输入
python fgwsz-package.py -c test.fgwsz a.txt subdir/ source/main.cpp

# 解包
python fgwsz-package.py -x test.fgwsz out

# 检查结果（示例）
# out/a.txt           (来自文件 a.txt)
# out/b.txt           (来自 subdir/b.txt，忽略子目录)
# out/source/main.cpp (来自目录 source/)
```

### 依赖项

- Python 3.6+
- 仅依赖 **Python 标准库**（无需第三方包）
- 构建时额外依赖 `pyinstaller`（自动安装）

---

## 📄 许可证

本项目采用 **MIT License** - 详见 [LICENSE](LICENSE) 文件。

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request。

1. Fork 本仓库
2. 创建你的功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交修改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 打开 Pull Request

---

## 📞 联系方式

如有问题，请在 GitHub 仓库中提交 Issue。

---

**Happy Packing!** 🚀
