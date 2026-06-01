---
name: go-next-move
description: Analyze a Go/Weiqi position from an image or board state, use KataGo to recommend the next move at beginner, intermediate, or advanced playing strength. Use when the user asks where black or white should play next, wants a move matched to an opponent's level, or wants AI-assisted handicap-like balancing without changing the board.
---

# Go Next Move

## Current Scope

This skill is being built as a separate move-selection layer from `count-go-black-stones`.

The intended workflow is:

1. Convert a board photo into a 19x19 position.
2. Ask the user or infer who is to move when possible.
3. Send the position to KataGo using Chinese rules and a fixed visit budget.
4. Return a recommended move matched to the requested playing-strength level.
5. Include candidate moves and enough analysis data to explain or audit the choice.

## Local KataGo Defaults

KataGo is installed through Homebrew and verified on this machine:

```bash
katago version
```

Expected important line:

```text
Using Metal backend
```

Use this project config after KataGo's bundled GTP config:

```bash
katago gtp \
  -model /opt/homebrew/share/katago/g170e-b20c256x2-s5303129600-d1228401921.bin.gz \
  -config /opt/homebrew/share/katago/configs/gtp_example.cfg \
  -config katago/gtp_skill.cfg
```

Set komi through GTP, not the config file:

```gtp
boardsize 19
komi 7.5
clear_board
genmove b
```

For scripted next-move analysis, prefer the JSON analysis engine:

```bash
python3 scripts/next_move.py /path/to/board.jpg \
  --input image \
  --side-to-move black \
  --level intermediate \
  --visits 400 \
  --overlay /tmp/go-next-overlay.jpg
```

For an already recognized board:

```bash
python3 scripts/next_move.py /path/to/board_ascii.txt \
  --input ascii \
  --side-to-move white \
  --level beginner
```

`board_ascii` is 19 rows of 19 characters:

- `X` or `B`: black stone
- `O` or `W`: white stone
- `.`: empty point

The script returns JSON containing:

- `board_ascii`
- `recommendation`
- `recommendations_by_level`
- `candidate_moves`
- `root_info`
- optional `recognition` metadata when input is an image

## Playing-Strength Levels

The level controls move strength, not explanation depth.

- Beginner: choose a plausible but intentionally softer move from KataGo's candidates. It should usually be playable, but may lose several points compared with the best move.
- Intermediate: choose a solid near-top candidate. It should be close to the best move but not always the engine's first choice.
- Advanced: choose KataGo's top searched candidate.

Use `--level all` when the caller wants all three recommendations at once. Use `recommendation` for the selected level and `recommendations_by_level` to compare the three outputs.

The current script chooses levels by candidate rank plus score/winrate loss from KataGo's best move. These thresholds are a practical first pass, not calibrated ranks. The next improvement should tune them with real game examples.

## Notes

- Do not rely on the language model alone for high-strength move choice.
- Use KataGo for candidate moves; use the requested level to choose the playing strength of the move.
- A board photo usually does not prove whose turn it is. Ask or require the side to move unless the surrounding context makes it clear.
- If board recognition is uncertain, surface the uncertainty before giving a move recommendation.
