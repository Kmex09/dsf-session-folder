# 数据恢复指南（DATA-RECOVERY.md）

DeepSeek Folder 的数据只存在两个地方，恢复也按「先易后难」的顺序：

1. **数据文件**：`%APPDATA%\DeepSeek Folder\deepseek-folder-data.json`
   （项目目录直接运行 `server.py` 时，是项目里的同名文件）
2. **上一版自动备份**：同目录下的 `deepseek-folder-data.bak.json`
3. **浏览器本地存储**：`%APPDATA%\DeepSeek Folder\Local Storage\leveldb\`（兜底）

---

## 情况一：刚误操作，`.bak.json` 还在

v0.5.5 起，**每次写入前**都会把上一版另存为 `deepseek-folder-data.bak.json`。
先关掉应用，然后：

```powershell
$dir = "$env:APPDATA\DeepSeek Folder"
Copy-Item "$dir\deepseek-folder-data.json" "$dir\deepseek-folder-data.before-restore.json" -Force
Copy-Item "$dir\deepseek-folder-data.bak.json" "$dir\deepseek-folder-data.json" -Force
```

再启动应用即可。

> 想「合并」而不是「覆盖」也可以：启动应用 →「导入备份」→ 选 `.bak.json` →
> 选 **合并到现有数据**（默认）。这也是最安全的做法。

## 情况二：`.bak.json` 也没有了

用 Chromium 的 LevelDB 里残留的历史值（本工具即用此法救回过数据）：

```powershell
# 1. 复制一份 leveldb（避免占用）
$src = "$env:APPDATA\DeepSeek Folder\Local Storage\leveldb"
$tmp = "$env:TEMP\df-leveldb-scan"
Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item $src $tmp -Recurse -Force

# 2. 用 Python 扫描 0000xx.log / .ldb，按 UTF-16LE 提取含 "folders"/"sessions" 的 JSON
python tools/recover-from-leveldb.py $tmp "$env:TEMP\df-recovered"
```

脚本会输出若干快照（按 `savedAt` 从新到旧），人工挑内容最全的那份，
再用「导入备份 → 合并」导入即可。原理：LevelDB 的写日志（`.log`）是追加式的，
同一个 key 的旧值在被压缩（compaction）之前仍然留在文件里。

## 情况三：只有导出的备份 JSON

「导入备份」→ 选文件 → **合并到现有数据**（v0.5.5 起为默认选项），
不会覆盖你当前的数据。

---

## 为什么会丢：v0.5.5 之前的设计缺陷

旧版「导入备份」直接 `data = 备份内容`（整体替换），且没有自动备份。
v0.5.5 起：

- 导入必须明确选择「合并 / 替换」，**默认合并**；
- 替换前服务端自动保留 `.bak.json`；
- 合并按链接去重，重复导入同一份备份不会产生重复会话。
