# Tinderbox 记忆库

本地优先的个人记忆库：把聊天、笔记、录音里的「决定 / 偏好 / 任务 / 知识」提炼成记忆，
按版本链管理「改口」，中文检索，原文冷存按需取回。

**一句话**：记忆是摘要，原文是证据；摘要可以失效，证据不能丢。

## 快速开始

`ash
git clone <repo>
cd <repo>
cp demo/.env.example demo/.env     # 填 LLM_API_KEY（可留空，会退回规则提炼）

python demo/run_demo.py            # 八步走查
python demo/selftest.py            # 12 项不变量
python demo/web.py                 # 看板 http://127.0.0.1:8777（首次访问要令牌）
`

零第三方依赖，Python 3.10+。令牌自动生成在 demo/.env 的 API_TOKEN。

## 这里有什么

| 目录/文件 | 内容 |
|---|---|
| Tinderbox_实施手册_v1.0 | **先看这个**：约 43 页，照着写代码 |
| Tinderbox_记忆库完整方案_v2.28 | 参考卷：完整设计、边界讨论、28 轮修订 |
| 测试报告_v1.0 | 12/12 通过、两次运行逐行一致 |
| 变更日志.md | 每一轮改了什么、为什么 |
| demo/ | 可运行实现（14 个脚本，含 12 项测试） |
| uild/ | 文档流水线：生成 → 校验 → 报告 |

## ⚠ 密钥

demo/.env **不入库**（已在 .gitignore）。里面是你的 LLM key 与看板令牌。
要提交前请确认 git status 里没有它。
