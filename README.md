# 围棋下一手推荐 Skill

[English README](README.en.md)

这是一个用于围棋 / Weiqi 的下一手推荐工具。它可以从棋盘图片或文本棋盘中识别当前局面，调用本地 KataGo 分析候选点，并按指定的**落子强度级别**选择下一手。

这里的 `初级`、`中级`、`高级` 指的是推荐手的强度，不是解释的深浅。这样可以在不同水平的对局里，让 AI 给出更适合对手水平的下一手，帮助对局更接近势均力敌。

## 功能

- 将 19 路围棋棋盘图片识别成 `board_ascii` 二维棋盘。
- 支持直接输入已有的 `board_ascii` 文本棋盘。
- 使用本地 KataGo 进行下一手分析。
- 输出 JSON，包含当前级别推荐手、三档级别推荐、候选手和根节点评估。
- 可选生成识别校验图，方便人工检查棋子识别是否准确。

## 环境要求

- Python 3.10+
- 本地已安装 KataGo
- KataGo 模型文件
- Python 依赖：

```bash
python3 -m pip install -r scripts/requirements.txt
```

本项目首先在 macOS + Homebrew KataGo 下测试：

```bash
brew install katago
katago version
```

脚本默认使用 Homebrew 自带模型路径：

```text
/opt/homebrew/share/katago/g170e-b20c256x2-s5303129600-d1228401921.bin.gz
```

如果你的模型在其他位置，运行时传入：

```bash
--model /path/to/model.bin.gz
```

## 图片输入

```bash
python3 scripts/next_move.py /path/to/board.jpg \
  --input image \
  --side-to-move black \
  --level intermediate \
  --visits 400 \
  --overlay /tmp/go-next-overlay.jpg
```

如果自动识别棋盘不准，可以手动传四个棋盘角点：

```bash
python3 scripts/next_move.py /path/to/board.jpg \
  --input image \
  --side-to-move white \
  --corners "74,76 1100,53 1118,1031 72,1034"
```

如果传入的是四个最外侧网格交叉点，而不是木质棋盘边角，再加：

```bash
--grid-corners
```

## 文本棋盘输入

`board_ascii` 每行表示棋盘一行：

```text
...................
...................
...................
...X...............
...................
...................
...................
...................
...................
...................
...................
...................
...................
...................
...................
...............O...
...................
...................
...................
```

字符含义：

- `X` 或 `B`：黑棋
- `O` 或 `W`：白棋
- `.`：空点

运行：

```bash
python3 scripts/next_move.py board_ascii.txt \
  --input ascii \
  --side-to-move black \
  --level beginner
```

也可以从 stdin 输入：

```bash
cat board_ascii.txt | python3 scripts/next_move.py \
  --input ascii \
  --side-to-move white \
  --level all
```

## 落子强度级别

- `beginner` / `初级`：选择一个能下但刻意更温和的 KataGo 候选手。
- `intermediate` / `中级`：选择一个接近最优的稳健候选手，但不总是第一推荐。
- `advanced` / `高级`：选择 KataGo 搜索排序第一的最强候选手。
- `all` / `全部`：同时返回三档级别推荐，方便比较。

当前分级策略使用候选手排序、相对最强手的目数损失和胜率损失来选择。这是第一版实用策略，不是严格校准过的段位模型。

## 输出

脚本输出 JSON。重要字段：

- `recommendation`：按 `--level` 选出的推荐手
- `recommendations_by_level`：初级、中级、高级三档推荐
- `candidate_moves`：KataGo 候选手，包含 visits、winrate、score lead 和 PV
- `root_info`：KataGo 根节点评估
- `board_ascii`：实际送入 KataGo 的棋盘
- `recognition`：图片识别元数据，仅图片输入时存在

输出形状示例：

```json
{
  "requested_level": "intermediate",
  "recommendation": {
    "move": "Q4",
    "strength_level": "intermediate",
    "score_loss_vs_best": 0.8,
    "winrate_loss_vs_best": 0.03
  },
  "recommendations_by_level": {
    "beginner": {},
    "intermediate": {},
    "advanced": {}
  }
}
```

## 只做棋盘识别

如果只想把图片转成二维棋盘：

```bash
python3 scripts/go_board_recognition.py /path/to/board.jpg \
  --overlay /tmp/go-recognition-overlay.jpg
```

## 注意

- 单张棋盘图片通常无法判断轮到谁下，所以必须传 `--side-to-move`。
- 图片模糊、倾斜、裁切、有覆盖标记时，识别可能出错。重要局面建议检查 `--overlay` 输出。
- 如果想要最强推荐，用 `--level advanced`，并适当增大 `--visits`。
