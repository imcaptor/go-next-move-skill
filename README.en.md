# Go Next Move Skill

Analyze a Go / Weiqi board position from an image or a text board, ask KataGo for candidate moves, and choose a next move at a requested playing-strength level.

The key idea is that `beginner`, `intermediate`, and `advanced` control **move strength**, not explanation depth. This can be used to make AI-assisted games more balanced against opponents of different levels.

## Features

- Recognize a 19x19 Go board image into `board_ascii`.
- Accept an existing `board_ascii` position from a text file or stdin.
- Use local KataGo for next-move analysis.
- Return JSON with the selected move, all level-based recommendations, candidate moves, and root evaluation.
- Optionally write a board recognition overlay image for visual checking.

## Requirements

- Python 3.10+
- KataGo installed locally
- A KataGo model file
- Python packages:

```bash
python3 -m pip install -r scripts/requirements.txt
```

This project was first tested on macOS with Homebrew KataGo:

```bash
brew install katago
katago version
```

The scripts default to Homebrew's bundled model path:

```text
/opt/homebrew/share/katago/g170e-b20c256x2-s5303129600-d1228401921.bin.gz
```

If your model is elsewhere, pass `--model /path/to/model.bin.gz`.

## Image Input

```bash
python3 scripts/next_move.py /path/to/board.jpg \
  --input image \
  --side-to-move black \
  --level intermediate \
  --visits 400 \
  --overlay /tmp/go-next-overlay.jpg \
  --source-overlay /tmp/go-source-overlay.jpg \
  --source-result-image /tmp/go-source-result.jpg \
  --result-image /tmp/go-next-result.jpg
```

`--source-overlay` marks detected stones and board corners on the original photo, which is the best user-facing recognition check. For photo input, the tool also generates a combined original-photo result by default: existing white stones are marked with black `W`, existing black stones are marked with white `B`, and the recommended move is drawn as a new stone with the numbered label `1`. If you also want a clean board image, pass `--result-image` explicitly. `--overlay` writes a warped/cropped board view for debugging.

If board detection needs help, pass four board corners:

```bash
python3 scripts/next_move.py /path/to/board.jpg \
  --input image \
  --side-to-move white \
  --corners "74,76 1100,53 1118,1031 72,1034"
```

If those points are the four outer grid intersections rather than the wooden board corners, add:

```bash
--grid-corners
```

## ASCII Input

`board_ascii` is one row per board line:

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

Characters:

- `X` or `B`: black stone
- `O` or `W`: white stone
- `.`: empty point

Run:

```bash
python3 scripts/next_move.py board_ascii.txt \
  --input ascii \
  --side-to-move black \
  --level beginner \
  --result-image /tmp/go-next-result.jpg
```

Or from stdin:

```bash
cat board_ascii.txt | python3 scripts/next_move.py \
  --input ascii \
  --side-to-move white \
  --level all
```

## Playing-Strength Levels

- `beginner`: choose a plausible but intentionally softer KataGo candidate.
- `intermediate`: choose a solid near-top candidate, not always the best move.
- `advanced`: choose KataGo's top searched candidate.
- `all`: return all three level recommendations for comparison.

The current selection policy uses candidate rank plus score and winrate loss from KataGo's best move. It is a practical first pass, not a calibrated rank model.

## Output

The script prints JSON. Important fields:

- `recommendation`: the move selected for `--level`
- `reason`: recommendation rationale, including selection basis, main variation, candidate comparison, and recognition caveats
- `recommendations_by_level`: beginner, intermediate, and advanced choices
- `candidate_moves`: KataGo candidates with visits, winrate, score lead, and PV
- `root_info`: KataGo root evaluation
- `board_ascii`: the position that was analyzed
- `recognition`: image recognition metadata, present only for image input
- `result_image`: path to the generated recommendation image, present only when you explicitly pass `--result-image`
- `source_result_image`: default combined original-photo image path for photo input, with existing stones marked by B/W text and the recommended move drawn as a numbered stone
- `recognition.source_overlay`: path to the source-photo recognition check, present only when `--source-overlay` is passed

Example shape:

```json
{
  "requested_level": "intermediate",
  "recommendation": {
    "move": "Q4",
    "strength_level": "intermediate",
    "score_loss_vs_best": 0.8,
    "winrate_loss_vs_best": 0.03
  },
  "reason": {
    "summary": "Recommended move for white: Q4. This is a near-best candidate selected for intermediate strength. Main line: Q4 -> D16 -> C17.",
    "main_variation": ["Q4", "D16", "C17"]
  },
  "recommendations_by_level": {
    "beginner": {},
    "intermediate": {},
    "advanced": {}
  }
}
```

## Board Recognition Only

To only convert an image into a 2D board:

```bash
python3 scripts/go_board_recognition.py /path/to/board.jpg \
  --source-overlay /tmp/go-source-overlay.jpg
```

## Notes

- A board image usually does not prove whose turn it is, so `--side-to-move` is required.
- Image recognition can be wrong on blurry, skewed, cropped, or heavily annotated boards. Check the overlay when accuracy matters.
- White-stone recognition checks more than brightness: it also requires low-saturation center evidence and center/ring contrast to reduce false positives from bright wood grain or glare.
- For high-strength play, use `--level advanced` with a larger `--visits` value.
