#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 Chromium Local Storage 的 LevelDB 中抢救 DeepSeek Folder 的数据快照。

用法：
    python tools/recover-from-leveldb.py <leveldb目录> <输出目录>

原理：
    LevelDB 的写日志（*.log）是追加式的。同一个 key（deepseek-folder.data.v1）
    在被 compaction 合并之前，历史值仍以 UTF-16LE 的形式留在文件里。
    本脚本按 UTF-16LE / UTF-8 两种解码各扫一遍，用括号匹配截出 JSON，
    再按 savedAt 从新到旧输出为 snapshot-*.json。

注意：
    这是**只读**工具，不会改动原目录；请先把 leveldb 目录复制一份再跑。
"""
import json
import os
import sys

KEY = 'deepseek-folder.data.v1'


def scan(text):
    """扫描一段解码后的文本，返回 {savedAt: obj}"""
    found = {}
    i = 0
    n = len(text)
    while True:
        i = text.find('{"v"', i)
        if i < 0:
            i = text.find('{"folders"', i)
        if i < 0:
            break
        depth = 0
        in_str = False
        esc = False
        j = i
        end = -1
        while j < n and j - i < 400000:
            ch = text[j]
            if in_str:
                if esc:
                    esc = False
                elif ch == '\\':
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        end = j + 1
                        break
            j += 1
        if end > 0:
            try:
                obj = json.loads(text[i:end])
            except Exception:
                obj = None
            if isinstance(obj, dict) and 'folders' in obj and 'sessions' in obj:
                found[int(obj.get('savedAt') or 0)] = obj
                i = end
                continue
        i += 1
    return found


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    src = sys.argv[1]
    outdir = sys.argv[2]
    if not os.path.isdir(src):
        print('目录不存在:', src)
        return 1
    os.makedirs(outdir, exist_ok=True)

    all_found = {}
    for name in sorted(os.listdir(src)):
        if not name.endswith(('.log', '.ldb')):
            continue
        raw = open(os.path.join(src, name), 'rb').read()
        all_found.update(scan(raw.decode('utf-16-le', errors='ignore')))
        all_found.update(scan(raw.decode('utf-8', errors='ignore')))

    if not all_found:
        print('没有找到可恢复的数据快照。')
        return 2

    print('找到 %d 个快照：' % len(all_found))
    for idx, (saved, obj) in enumerate(sorted(all_found.items(), reverse=True)):
        folders = [f.get('name') for f in obj.get('folders', [])]
        sessions = obj.get('sessions', [])
        out = os.path.join(outdir, 'snapshot-%02d-savedAt-%d.json' % (idx, saved))
        with open(out, 'w', encoding='utf-8') as fh:
            json.dump(obj, fh, ensure_ascii=False, indent=2)
        print('  #%d savedAt=%d folders=%d sessions=%d' % (idx, saved, len(folders), len(sessions)))
        print('      文件夹: %s' % ' / '.join(str(x) for x in folders[:10]))
        print('      文件  : %s' % out)
    print('\n挑内容最全的一份，在应用里「导入备份」→ 选「合并到现有数据」。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
