# 📚 文档索引

欢迎！这是 interactive-storybook 项目的完整文档索引。

## 🚨 快速开始（按需选择）

### 场景 1: 第一次遇到问题

**👉 从这里开始**: [`README_FIXES.md`](README_FIXES.md)
- ⏱️ 阅读时间：2 分钟
- 🎯 内容：快速诊断和一键修复
- ✅ 适合：刚遇到错误，需要立即解决

### 场景 2: 想快速了解所有命令

**👉 查看**: [`CHEAT_SHEET.md`](CHEAT_SHEET.md)
- ⏱️ 阅读时间：1 分钟
- 🎯 内容：所有关键命令速查表
- ✅ 适合：已经了解问题，只需要命令

### 场景 3: 需要了解 jimeng-api 使用方法

**👉 阅读**: [`JIMENG_API_GUIDE.md`](JIMENG_API_GUIDE.md)
- ⏱️ 阅读时间：10 分钟
- 🎯 内容：基于官方文档的完整使用指南
- ✅ 适合：想深入了解 jimeng-api 的使用和排查

### 场景 4: 想了解所有问题的完整技术细节

**👉 深入**: [`ECS_DEPLOYMENT_FIXES.md`](ECS_DEPLOYMENT_FIXES.md)
- ⏱️ 阅读时间：15 分钟
- 🎯 内容：所有问题的技术分析和修复方案
- ✅ 适合：想全面了解部署中的所有问题

---

## 📖 文档清单

### 核心文档（必读）

| 文档 | 内容 | 阅读时间 | 优先级 |
|------|------|----------|--------|
| [`README_FIXES.md`](README_FIXES.md) | 🚨 快速修复指南 | 2 分钟 | ⭐⭐⭐ |
| [`CHEAT_SHEET.md`](CHEAT_SHEET.md) | ⚡ 命令速查表 | 1 分钟 | ⭐⭐⭐ |
| [`JIMENG_API_GUIDE.md`](JIMENG_API_GUIDE.md) | 📖 jimeng-api 完整指南 | 10 分钟 | ⭐⭐ |

### 详细文档（深入了解）

| 文档 | 内容 | 阅读时间 | 优先级 |
|------|------|----------|--------|
| [`ECS_DEPLOYMENT_FIXES.md`](ECS_DEPLOYMENT_FIXES.md) | 🔧 完整修复汇总 | 15 分钟 | ⭐⭐ |
| [`FINAL_FIX.md`](FINAL_FIX.md) | 🔍 最终问题定位 | 10 分钟 | ⭐⭐ |
| [`QUICK_FIX_GUIDE.md`](QUICK_FIX_GUIDE.md) | ⚡ 3分钟快速修复 | 3 分钟 | ⭐⭐ |
| [`FIX_SUMMARY.md`](FIX_SUMMARY.md) | 🛠️ OpenAI 客户端修复 | 8 分钟 | ⭐ |
| [`fix-jimeng-502.md`](fix-jimeng-502.md) | 🐛 502 错误详细诊断 | 12 分钟 | ⭐ |

---

## 🔧 脚本清单

### 修复脚本

| 脚本 | 功能 | 使用时机 |
|------|------|----------|
| [`deploy-fix.sh`](deploy-fix.sh) | 修复 OpenAI 客户端问题 | SOCKS 代理错误、httpx 错误 |
| [`fix-docker-env.sh`](fix-docker-env.sh) | 修复 Docker 环境变量 | 502 错误、环境变量未传递 |
| [`fix-jimeng.sh`](fix-jimeng.sh) | 通用故障排查 | 图片生成失败 |
| [`update-sessionid.sh`](update-sessionid.sh) | 更新 SessionID | Token 过期、live: false |

### 测试和管理脚本

| 脚本 | 功能 | 使用时机 |
|------|------|----------|
| [`test-jimeng-api.sh`](test-jimeng-api.sh) | 完整 API 测试 | 验证所有功能是否正常 |
| [`restart.sh`](restart.sh) | 重启所有服务 | 日常重启、配置更新后 |

---

## 🎯 按问题类型查找

### 问题：502 Bad Gateway

**诊断流程**：
1. 先运行：[`test-jimeng-api.sh`](test-jimeng-api.sh)
2. 如果环境变量缺失，运行：[`fix-docker-env.sh`](fix-docker-env.sh)
3. 如果 Token 无效，运行：[`update-sessionid.sh`](update-sessionid.sh)

**参考文档**：
- [`FINAL_FIX.md`](FINAL_FIX.md) - 502 错误根本原因分析
- [`fix-jimeng-502.md`](fix-jimeng-502.md) - 502 错误详细诊断
- [`JIMENG_API_GUIDE.md`](JIMENG_API_GUIDE.md) - 常见问题排查

### 问题：SOCKS proxy 错误

**解决方案**：
1. 运行：[`deploy-fix.sh`](deploy-fix.sh)
2. 重启服务

**参考文档**：
- [`FIX_SUMMARY.md`](FIX_SUMMARY.md) - OpenAI 客户端详细修复

### 问题：Token 过期 (live: false)

**解决方案**：
1. 运行：[`update-sessionid.sh`](update-sessionid.sh)
2. 按提示粘贴新的 SessionID

**参考文档**：
- [`JIMENG_API_GUIDE.md`](JIMENG_API_GUIDE.md) - SessionID 管理章节

### 问题：不知道从哪里开始

**推荐流程**：
1. 阅读：[`README_FIXES.md`](README_FIXES.md)（2分钟）
2. 运行：[`test-jimeng-api.sh`](test-jimeng-api.sh)（查看具体问题）
3. 根据测试结果，运行对应的修复脚本
4. 再次运行测试验证

---

## 📊 文档关系图

```
开始
  ├─ 快速修复 → README_FIXES.md
  │              ├─ 运行脚本 → deploy-fix.sh + fix-docker-env.sh
  │              └─ 验证 → test-jimeng-api.sh
  │
  ├─ 命令查询 → CHEAT_SHEET.md
  │
  ├─ 深入了解 jimeng-api → JIMENG_API_GUIDE.md
  │                          ├─ 官方 API 文档
  │                          ├─ 故障排查
  │                          └─ 最佳实践
  │
  └─ 技术细节 → ECS_DEPLOYMENT_FIXES.md
                 ├─ 问题 1&2 → FIX_SUMMARY.md
                 ├─ 问题 3 → FINAL_FIX.md
                 └─ 502 详解 → fix-jimeng-502.md
```

---

## 🌟 推荐阅读顺序

### 初次部署遇到问题

1. [`README_FIXES.md`](README_FIXES.md) - 了解问题和快速修复
2. [`CHEAT_SHEET.md`](CHEAT_SHEET.md) - 记住关键命令
3. [`test-jimeng-api.sh`](test-jimeng-api.sh) - 运行完整测试
4. 根据测试结果查看对应的详细文档

### 想深入了解

1. [`ECS_DEPLOYMENT_FIXES.md`](ECS_DEPLOYMENT_FIXES.md) - 所有问题汇总
2. [`JIMENG_API_GUIDE.md`](JIMENG_API_GUIDE.md) - jimeng-api 深度指南
3. [`FINAL_FIX.md`](FINAL_FIX.md) - 最新问题分析
4. [`FIX_SUMMARY.md`](FIX_SUMMARY.md) - 客户端优化细节

### 日常维护

1. [`CHEAT_SHEET.md`](CHEAT_SHEET.md) - 快速查找命令
2. [`test-jimeng-api.sh`](test-jimeng-api.sh) - 定期测试
3. [`update-sessionid.sh`](update-sessionid.sh) - SessionID 更新

---

## 💡 使用技巧

### 1. 善用搜索

在任何文档中搜索关键词：
```bash
# 搜索 "502"
grep -r "502" *.md

# 搜索 "SessionID"
grep -r "SessionID" *.md
```

### 2. 文档间跳转

所有文档都有相互链接，点击文件名可以快速跳转。

### 3. 保持更新

```bash
# 拉取最新文档
git pull

# 查看更新内容
git log --oneline --all --graph -10
```

### 4. 添加书签

在浏览器中为常用文档添加书签：
- README_FIXES.md
- CHEAT_SHEET.md
- JIMENG_API_GUIDE.md

---

## 🔗 外部资源

| 资源 | 链接 |
|------|------|
| jimeng-api 官方仓库 | https://github.com/iptag/jimeng-api |
| jimeng-api 官方文档 | https://github.com/iptag/jimeng-api/blob/main/README.CN.md |
| Telegram 交流群 | https://t.me/jimeng_api |
| 即梦官网 | https://jimeng.jianying.com/ |
| Dreamina 国际站 | https://www.dreamina.com/ |

---

## 📞 反馈和贡献

如果发现文档问题或有改进建议：

1. 提交 Issue
2. 提交 Pull Request
3. 在 Telegram 群组讨论

---

## 📅 更新日志

- **2026-02-11**: 创建完整文档索引
- 基于官方文档完善所有指南
- 添加测试脚本和修复脚本
- 建立文档关系和推荐阅读顺序

---

## ✨ 快速命令汇总

```bash
# 一键修复
git pull && bash deploy-fix.sh && bash fix-docker-env.sh

# 完整测试
bash test-jimeng-api.sh

# 查看日志
tail -f logs/backend.log

# 重启服务
bash restart.sh
```

**开始修复？→ [`README_FIXES.md`](README_FIXES.md)**
