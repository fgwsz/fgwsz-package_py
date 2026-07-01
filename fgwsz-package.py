#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
# fgwsz-package - 打包/解包工具（XOR 混淆版）
=============================================

功能概述
--------
本工具用于将多个文件/目录归档为单一的 `.fgwsz` 包文件。
每个文件条目在包内使用**单字节随机 XOR** 进行混淆，以防止轻易识别文件结构。
工具支持打包、解包、列表查看三种操作模式。

路径存储规则
------------
- **文件输入**：包内路径仅存储文件名（不含任何父目录），解包时文件直接放入输出根目录。
- **目录输入**：包内路径存储为 `目录名/子文件路径`，解包时完整保留目录结构。
- **符号链接**：打包时自动跳过所有符号链接，不打包链接本身，也不跟随链接目标。

包格式（二进制结构）
--------------------
每个文件条目存储结构：
    [KEY (1 byte)]           // 随机密钥（1~255），明文存储
    [PATH_LEN (8 bytes)]     // 路径长度，大端序，使用 KEY 异或混淆
    [PATH (N bytes)]         // 路径字符串（UTF-8），使用 KEY 异或混淆
    [CONTENT_LEN (8 bytes)]  // 内容长度，大端序，使用 KEY 异或混淆
    [CONTENT (M bytes)]      // 文件原始二进制内容，使用 KEY 异或混淆

特别注意
--------
- 所有长度字段均为 **8 字节无符号大端整数**（网络字节序），与 C++ 版本一致。
- 路径在包内统一使用正斜杠 `/`（跨平台兼容）。
- 混淆仅提供 **轻微混淆**，不保证强加密（仅为防止直接读取）。
- 打包目录时，始终包含目录自身（即相对路径以目录名开头）。
- 目录路径末尾的 `/` 不会影响打包行为（会被自动规范化）。
- 打包生成的 `.fgwsz` 文件会被自动设置为只读权限。

使用示例
--------
    # 打包单个文件（解包时文件直接放入输出根目录）
    python fgwsz-package.py -c out.fgwsz README.md

    # 打包目录（保留目录结构）
    python fgwsz-package.py -c out.fgwsz source/

    # 混合打包文件与目录
    python fgwsz-package.py -c out.fgwsz README.md source/ doc/guide.txt

    # 解包到 output 目录
    python fgwsz-package.py -x out.fgwsz output

    # 列表查看包内容
    python fgwsz-package.py -l out.fgwsz

兼容性
------
- 本 Python 实现与 C++ 原版 `fgwsz-package` **完全二进制兼容**，可互相读取/写入。
- 仅依赖 Python 标准库（无需 pip 安装任何第三方包）。
- 支持 Windows、Linux、macOS。

许可证
-------
本项目指定 MIT 许可证
"""

import os
import sys
import argparse
import struct
import pathlib
import random
from typing import List

# -------------------------- 常量 --------------------------
PACKAGE_EXT = ".fgwsz"      # 推荐的包文件扩展名
LENGTH_SIZE = 8             # 长度字段占用的字节数（8 字节大端）
KEY_SIZE = 1                # 混淆密钥占用的字节数
BLOCK_SIZE = 8 * 1024 * 1024  # 分块大小（8MB），用于大文件读写


# -------------------------- 工具函数 --------------------------

def build_xor_table(key: int) -> bytes:
    """
    构建用于 bytes.translate 的 XOR 转换表。

    :param key: 1~255 的混淆密钥
    :return: 长度为 256 的 bytes 对象，其中 table[i] = i ^ key
    """
    return bytes([i ^ key for i in range(256)])


def xor_bytes(data: bytes, key: int) -> bytes:
    """
    使用给定的密钥对 bytes 数据进行 XOR 混淆。

    该函数通过 bytes.translate 实现，底层由 C 语言完成，速度极快。

    :param data: 待混淆的原始字节
    :param key: 1~255 的密钥
    :return: 混淆后的字节
    """
    if key == 0:
        return data
    return data.translate(build_xor_table(key))


def normalize_path_for_package(path: str) -> str:
    """
    将操作系统路径格式化为包内存储的标准格式。

    统一使用正斜杠 '/'。

    :param path: 原始路径字符串
    :return: 使用正斜杠的标准化路径
    """
    return str(pathlib.PurePath(path).as_posix())


# -------------------------- 打包功能 --------------------------

def pack_files(input_paths: List[str], output_package: str) -> None:
    """
    将多个文件/目录打包到 .fgwsz 包中。

    路径存储规则：
        - 如果输入是文件：包内路径仅为文件名（不含目录路径），解包时文件直接放入输出根目录。
        - 如果输入是目录：包内路径为 "目录名/子文件路径"，解包时保留目录结构。

    打包流程：
        1. 递归遍历所有输入路径，收集所有普通文件及其相对路径。
        2. 对每个文件，生成随机密钥（1~255）。
        3. 按规范写入：密钥 → 混淆后的路径长度 → 混淆后的路径 → 混淆后的内容长度 → 混淆后的内容。

    注意：打包成功后，输出文件会被设置为只读权限（所有用户只读），防止意外修改。

    :param input_paths: 命令行输入的路径列表（文件和/或目录）
    :param output_package: 输出的包文件路径
    """
    items_to_pack = []  # 存放 (relative_path_str, absolute_file_path)

    # ----- 遍历输入路径，收集所有待打包文件 -----
    for raw_path in input_paths:
        p = pathlib.Path(raw_path)
        if not p.exists():
            print(f"警告: 路径不存在，已跳过: {raw_path}")
            continue

        if p.is_file():
            # 如果是符号链接指向的文件，跳过
            if p.is_symlink():
                print(f"警告: 跳过符号链接文件: {raw_path}")
                continue

            # 直接输入的文件：仅使用文件名（不含目录路径）
            items_to_pack.append((p.name, p))
        else:
            # 目录处理：打包目录自身（包含目录名）
            # 使用 os.walk 遍历，默认不跟随符号链接
            for root, dirs, files in os.walk(p):
                root_path = pathlib.Path(root)
                for file in files:
                    file_path = root_path / file
                    # 跳过符号链接文件
                    if file_path.is_symlink():
                        continue
                    # 相对路径以目录名开头
                    rel = file_path.relative_to(p.parent)
                    items_to_pack.append((normalize_path_for_package(str(rel)), file_path))

    if not items_to_pack:
        print("没有找到任何文件，打包终止。")
        return

    # 按相对路径排序，使包内容有序（便于阅读和比对）
    items_to_pack.sort(key=lambda x: x[0])

    # ----- 开始写入包文件 -----
    with open(output_package, 'wb') as f_out:
        for rel_path, file_path in items_to_pack:
            # 1. 生成随机密钥（1~255，避免 0 导致无混淆）
            key = random.randint(1, 255)

            # 2. 写入密钥（明文）
            f_out.write(bytes([key]))

            # 3. 处理路径字段
            path_bytes = rel_path.encode('utf-8')
            path_len = len(path_bytes)

            # 路径长度 → 8 字节大端 → XOR 混淆
            path_len_be = struct.pack('>Q', path_len)
            path_len_enc = xor_bytes(path_len_be, key)
            f_out.write(path_len_enc)

            # 路径字符串 → XOR 混淆
            path_enc = xor_bytes(path_bytes, key)
            f_out.write(path_enc)

            # 4. 处理内容字段
            content_len = os.path.getsize(file_path)

            # 内容长度 → 8 字节大端 → XOR 混淆
            content_len_be = struct.pack('>Q', content_len)
            content_len_enc = xor_bytes(content_len_be, key)
            f_out.write(content_len_enc)

            # 内容数据分块 XOR 并写入（避免一次性加载整个文件）
            table = build_xor_table(key)
            with open(file_path, 'rb') as f_in:
                while True:
                    chunk = f_in.read(BLOCK_SIZE)
                    if not chunk:
                        break
                    # 使用 translate 实现快速 XOR
                    enc_chunk = chunk.translate(table)
                    f_out.write(enc_chunk)

    print(f"打包完成，输出文件: {output_package}")
    print(f"共打包 {len(items_to_pack)} 个文件。")

    # ----- 设置包文件为只读（防止意外修改） -----
    try:
        Path(output_package).chmod(0o444)
    except Exception as e:
        print(f"警告: 设置只读权限失败: {e}")


# -------------------------- 解包功能 --------------------------

def unpack_package(input_package: str, output_dir: str) -> None:
    """
    从 .fgwsz 包中解压所有文件到指定目录。

    解包流程：
        1. 按顺序读取每个文件条目：密钥 → 路径长度 → 路径 → 内容长度 → 内容。
        2. 使用密钥对长度和数据进行 XOR 解密。
        3. 根据相对路径创建文件及父目录。

    :param input_package: 输入的包文件路径
    :param output_dir: 解包输出根目录
    """
    if not os.path.isfile(input_package):
        print(f"错误: 包文件不存在: {input_package}")
        return

    out_root = pathlib.Path(output_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    file_count = 0
    with open(input_package, 'rb') as f_in:
        while True:
            # ----- 1. 读取密钥 -----
            key_byte = f_in.read(KEY_SIZE)
            if not key_byte:
                break
            if len(key_byte) < KEY_SIZE:
                print("警告: 文件格式不完整（缺少密钥），提前终止。")
                break
            key = key_byte[0]

            # ----- 2. 读取并解密路径长度 -----
            len_be = f_in.read(LENGTH_SIZE)
            if len(len_be) < LENGTH_SIZE:
                print("警告: 路径长度字段不完整，提前终止。")
                break
            path_len_be_dec = xor_bytes(len_be, key)
            path_len = struct.unpack('>Q', path_len_be_dec)[0]

            # ----- 3. 读取并解密路径字符串 -----
            path_enc = f_in.read(path_len)
            if len(path_enc) < path_len:
                print("警告: 路径数据不完整，提前终止。")
                break
            path_bytes = xor_bytes(path_enc, key)
            rel_path = path_bytes.decode('utf-8')

            # ----- 4. 读取并解密内容长度 -----
            len_be = f_in.read(LENGTH_SIZE)
            if len(len_be) < LENGTH_SIZE:
                print("警告: 内容长度字段不完整，提前终止。")
                break
            content_len_be_dec = xor_bytes(len_be, key)
            content_len = struct.unpack('>Q', content_len_be_dec)[0]

            # ----- 5. 读取并解密内容数据（分块写入目标文件） -----
            target_path = out_root / rel_path
            target_path.parent.mkdir(parents=True, exist_ok=True)

            table = build_xor_table(key)
            with open(target_path, 'wb') as f_out:
                remaining = content_len
                while remaining > 0:
                    chunk_size = min(remaining, BLOCK_SIZE)
                    chunk_enc = f_in.read(chunk_size)
                    if not chunk_enc:
                        break
                    chunk_dec = chunk_enc.translate(table)
                    f_out.write(chunk_dec)
                    remaining -= len(chunk_enc)

                if remaining != 0:
                    print(f"警告: 文件 {rel_path} 内容读取不完整（剩余 {remaining} 字节）")

            file_count += 1

    print(f"解包完成，输出目录: {output_dir}")
    print(f"共解包 {file_count} 个文件。")


# -------------------------- 列表查看功能 --------------------------

def list_package(input_package: str) -> None:
    """
    列出 .fgwsz 包内所有文件的相对路径和大小（已解密显示）。

    不读取实际文件内容，仅解析头部信息，因此速度快。

    :param input_package: 包文件路径
    """
    if not os.path.isfile(input_package):
        print(f"错误: 包文件不存在: {input_package}")
        return

    file_count = 0
    total_size = 0
    with open(input_package, 'rb') as f_in:
        while True:
            key_byte = f_in.read(KEY_SIZE)
            if not key_byte:
                break
            if len(key_byte) < KEY_SIZE:
                break
            key = key_byte[0]

            len_be = f_in.read(LENGTH_SIZE)
            if len(len_be) < LENGTH_SIZE:
                break
            path_len_be_dec = xor_bytes(len_be, key)
            path_len = struct.unpack('>Q', path_len_be_dec)[0]

            path_enc = f_in.read(path_len)
            if len(path_enc) < path_len:
                break
            path_bytes = xor_bytes(path_enc, key)
            rel_path = path_bytes.decode('utf-8')

            len_be = f_in.read(LENGTH_SIZE)
            if len(len_be) < LENGTH_SIZE:
                break
            content_len_be_dec = xor_bytes(len_be, key)
            content_len = struct.unpack('>Q', content_len_be_dec)[0]

            f_in.seek(content_len, os.SEEK_CUR)

            file_count += 1
            total_size += content_len
            print(f"{rel_path}  ({content_len} bytes)")

    print(f"\n总计: {file_count} 个文件, 总大小: {total_size} 字节")


# -------------------------- 命令行入口 --------------------------

def main() -> None:
    """
    命令行入口，解析参数并调用相应功能。
    """
    parser = argparse.ArgumentParser(
        description="fgwsz-package - 打包/解包工具，使用单字节 XOR 混淆",
        epilog="示例: %(prog)s -c out.fgwsz file1 dir  # 打包"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-c', nargs='+', metavar='PATH',
                       help='打包模式: -c 输出包名 输入路径1 [输入路径2 ...]')
    group.add_argument('-x', nargs=2, metavar=('PACKAGE', 'OUT_DIR'),
                       help='解包模式: -x 包文件 输出目录')
    group.add_argument('-l', nargs=1, metavar='PACKAGE',
                       help='列表模式: -l 包文件')

    args = parser.parse_args()

    if args.c is not None:
        if len(args.c) < 2:
            print("错误: -c 需要至少两个参数: 输出包名 和 至少一个输入路径")
            sys.exit(1)
        output_pkg = args.c[0]
        input_paths = args.c[1:]
        pack_files(input_paths, output_pkg)

    elif args.x is not None:
        pkg_file, out_dir = args.x
        unpack_package(pkg_file, out_dir)

    elif args.l is not None:
        pkg_file = args.l[0]
        list_package(pkg_file)


if __name__ == '__main__':
    main()
