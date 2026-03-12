# 订阅费用计算器

命令行工具，用于管理订阅费用，支持跨货币（CNY/USD）和跨周期（day/month/quarter/year）统一换算。

## 环境要求

| 组件 | 版本要求 | 用途 |
|------|----------|------|
| Python | 3.10+ | 用到了 `float \| None` 类型注解 |
| Flask | 任意新版 | Web UI 后端（CLI 不需要） |

### Arch Linux 安装

```bash
# Python（通常已预装）
sudo pacman -S python

# 方案 A：用 pacman 安装 Flask（系统级，推荐）
sudo pacman -S python-flask

# 方案 B：用虚拟环境（不污染系统）
python -m venv .venv
source .venv/bin/activate   # bash/zsh
# source .venv/bin/activate.fish   # fish
pip install -r requirements.txt
```

### 其他发行版 / macOS

```bash
pip install -r requirements.txt
```

## 文件结构

```
.
├── main.py          # CLI 主程序
├── web.py           # Flask Web 后端
├── templates/
│   └── index.html   # 单页前端
├── start.sh         # 一键启动 Web UI（自动创建 venv）
├── requirements.txt # Python 依赖
├── data.json        # 订阅数据（运行时自动创建，不纳入 git）
└── README.md
```

## 快速开始

```bash
# 列出所有订阅
python main.py list

# 新增订阅：名称 金额 周期 货币
python main.py add "Netflix" 15.99 month USD
python main.py add "iCloud"  21    month CNY

# 删除序号为 2 的订阅（序号来自 list 输出）
python main.py delete 2

# 汇总：默认换算为 CNY/月（实时汇率）
python main.py summary

# 汇总：换算为 USD/年
python main.py summary -c USD -p year

# 汇总：手动指定汇率（1 USD = 7.25 CNY）
python main.py summary -c CNY -p month --rate 7.25
```

## 命令说明

| 命令 | 参数 | 说明 |
|------|------|------|
| `add` | `名称 金额 周期 货币` | 新增订阅 |
| `list` | — | 列出所有订阅 |
| `delete` | `序号` | 按序号删除订阅 |
| `summary` | `[-c CNY\|USD] [-p day\|month\|quarter\|year] [-r 汇率]` | 换算并统计总费用 |

## 换算规则

**周期换算**（统一以天为基准）：

| 周期 | 天数 |
|------|------|
| day | 1 |
| month | 30 |
| quarter | 90 |
| year | 360 |

**货币换算**：

- 默认联网从 [open.er-api.com](https://open.er-api.com) 获取实时 USD/CNY 汇率
- `--rate` 参数可手动指定汇率，优先于实时汇率

## Web UI

```bash
# 安装依赖后启动（见上方「环境要求」）
python web.py        # 默认 http://localhost:5000

# 或用一键脚本（自动创建 venv，首次运行会安装依赖）
./start.sh
```

功能：
- 页面新增 / 删除订阅，与 CLI 共用同一份 `data.json`
- 饼图按换算后金额展示各订阅占比
- 支持切换目标货币、目标周期
- 实时汇率（open.er-api.com），也可手动填写汇率
- 支持系统暗色模式

## 示例输出

```
$ python main.py list
#   名称                        金额  货币  周期        添加日期
─────────────────────────────────────────────────────────────
1   Netflix                    15.99  USD   month       2025-01-01
2   Spotify                     9.99  USD   month       2025-01-01
3   iCloud 200GB               21.00  CNY   month       2025-01-01
4   域名续费                   88.00  CNY   year        2025-03-01
5   GitHub Copilot            100.00  USD   year        2025-02-15

$ python main.py summary -c CNY -p month
  汇率（实时）：1 USD = 7.2650 CNY

────────────────────────────────────────────────────────────
  汇总  —  目标：CNY / month
────────────────────────────────────────────────────────────
  #   名称                        原始金额        换算金额
  ────────────────────────────────────────────────────────
  1   Netflix             15.99 USD/month    ¥116.18/月
  2   Spotify              9.99 USD/month     ¥72.56/月
  3   iCloud 200GB        21.00 CNY/month     ¥21.00/月
  4   域名续费            88.00 CNY/year       ¥7.33/月
  5   GitHub Copilot     100.00 USD/year      ¥60.54/月
  ────────────────────────────────────────────────────────
  合计                                       ¥277.61/月
────────────────────────────────────────────────────────────
```
