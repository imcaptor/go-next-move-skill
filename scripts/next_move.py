#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

from go_board_recognition import recognize_board, render_overlay, write_image


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = "/opt/homebrew/share/katago/g170e-b20c256x2-s5303129600-d1228401921.bin.gz"
DEFAULT_ANALYSIS_CONFIG = "/opt/homebrew/share/katago/configs/analysis_example.cfg"
DEFAULT_SKILL_CONFIG = Path("katago") / "analysis_skill.cfg"
GTP_COLUMNS = "ABCDEFGHJKLMNOPQRSTUVWXYZ"
LEVEL_ALIASES = {
    "beginner": "beginner",
    "初级": "beginner",
    "low": "beginner",
    "intermediate": "intermediate",
    "中级": "intermediate",
    "medium": "intermediate",
    "advanced": "advanced",
    "高级": "advanced",
    "high": "advanced",
    "all": "all",
    "全部": "all",
}


def normalize_player(raw: str) -> str:
    value = raw.strip().lower()
    if value in {"b", "black", "黑", "黑棋"}:
        return "B"
    if value in {"w", "white", "白", "白棋"}:
        return "W"
    raise SystemExit("--side-to-move must be black/B/黑 or white/W/白")


def gtp_coord(row: int, col: int, board_size: int) -> str:
    if col >= len(GTP_COLUMNS):
        raise SystemExit(f"Board size {board_size} is too large for the built-in GTP column table")
    return f"{GTP_COLUMNS[col]}{board_size - row}"


def parse_board_ascii(text: str) -> list[str]:
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        compact = "".join(ch for ch in line if not ch.isspace())
        if compact:
            rows.append(compact)
    if not rows:
        raise SystemExit("No board_ascii rows found")
    size = len(rows)
    bad_rows = [idx + 1 for idx, row in enumerate(rows) if len(row) != size]
    if bad_rows:
        raise SystemExit(f"board_ascii must be square; bad row(s): {bad_rows}")
    allowed = set("XxBbOoWw.")
    for idx, row in enumerate(rows, start=1):
        bad = sorted(set(row) - allowed)
        if bad:
            raise SystemExit(f"Unsupported board_ascii character(s) on row {idx}: {''.join(bad)}")
    return rows


def board_ascii_to_initial_stones(rows: list[str]) -> list[list[str]]:
    size = len(rows)
    stones: list[list[str]] = []
    for row_idx, row in enumerate(rows):
        for col_idx, value in enumerate(row):
            if value in {"X", "x", "B", "b"}:
                stones.append(["B", gtp_coord(row_idx, col_idx, size)])
            elif value in {"O", "o", "W", "w"}:
                stones.append(["W", gtp_coord(row_idx, col_idx, size)])
    return stones


def load_board_source(args: argparse.Namespace) -> tuple[list[str], dict[str, Any] | None]:
    source = Path(args.source) if args.source else None
    input_kind = args.input
    if input_kind == "auto":
        if source and source.exists() and source.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}:
            input_kind = "image"
        else:
            input_kind = "ascii"

    if input_kind == "image":
        if source is None:
            raise SystemExit("Image input requires a source image path")
        recognition, warped, board, xfit, yfit = recognize_board(
            source,
            board_size=args.board_size,
            warp_size=args.warp_size,
            corners=args.corners,
            grid_corners=args.grid_corners,
        )
        if args.overlay:
            write_image(args.overlay, render_overlay(warped, board, xfit, yfit))
            recognition["overlay"] = str(args.overlay)
        return list(recognition["board_ascii"]), recognition

    if source:
        text = source.read_text(encoding="utf-8")
    else:
        text = sys.stdin.read()
    return parse_board_ascii(text), None


def run_katago_analysis(
    rows: list[str],
    side_to_move: str,
    komi: float,
    visits: int,
    katago: str,
    model: str,
    config: str,
    skill_config: Path,
) -> dict[str, Any]:
    skill_config_arg = str(skill_config)
    if skill_config.is_absolute():
        try:
            skill_config_arg = str(skill_config.relative_to(REPO_ROOT))
        except ValueError:
            raise SystemExit("KataGo analysis does not accept an absolute project override config path; pass a path relative to this project")

    query = {
        "id": f"go-next-move-{uuid.uuid4().hex}",
        "initialStones": board_ascii_to_initial_stones(rows),
        "initialPlayer": side_to_move,
        "moves": [],
        "rules": "chinese",
        "komi": komi,
        "boardXSize": len(rows),
        "boardYSize": len(rows),
        "analyzeTurns": [0],
        "maxVisits": visits,
        "includePVVisits": True,
        "analysisPVLen": 8,
    }
    command = [
        katago,
        "analysis",
        "-model",
        model,
        "-config",
        config,
        "-config",
        skill_config_arg,
    ]
    proc = subprocess.run(
        command,
        input=json.dumps(query, ensure_ascii=False) + "\n",
        text=True,
        capture_output=True,
        cwd=REPO_ROOT,
        timeout=max(30, int(visits / 20) + 25),
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(
            "KataGo analysis failed.\n"
            f"Command: {' '.join(command)}\n"
            f"stderr:\n{proc.stderr.strip()}"
        )

    final_response = None
    warnings = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "error" in payload:
            raise SystemExit(f"KataGo returned an error: {payload['error']}")
        if "warning" in payload:
            warnings.append(payload["warning"])
            continue
        if payload.get("id") == query["id"] and payload.get("isDuringSearch") is False:
            final_response = payload

    if final_response is None:
        raise SystemExit(f"KataGo returned no final analysis response. stderr:\n{proc.stderr.strip()}")
    if warnings:
        final_response.setdefault("warnings", []).extend(warnings)
    return final_response


def slim_move_info(move: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "move",
        "order",
        "visits",
        "edgeVisits",
        "winrate",
        "scoreLead",
        "scoreMean",
        "scoreStdev",
        "prior",
        "lcb",
        "utility",
        "pv",
        "pvVisits",
        "pvEdgeVisits",
    ]
    return {key: move[key] for key in keys if key in move}


def normalize_level(raw: str) -> str:
    value = raw.strip().lower()
    if value in LEVEL_ALIASES:
        return LEVEL_ALIASES[value]
    raise SystemExit("--level must be beginner/初级, intermediate/中级, advanced/高级, or all/全部")


def score_loss(best: dict[str, Any], move: dict[str, Any]) -> float | None:
    if "scoreLead" not in best or "scoreLead" not in move:
        return None
    return max(0.0, float(best["scoreLead"]) - float(move["scoreLead"]))


def winrate_loss(best: dict[str, Any], move: dict[str, Any]) -> float | None:
    if "winrate" not in best or "winrate" not in move:
        return None
    return max(0.0, float(best["winrate"]) - float(move["winrate"]))


def annotate_strength(best: dict[str, Any], move: dict[str, Any], level: str, reason: str) -> dict[str, Any]:
    annotated = dict(move)
    loss = score_loss(best, move)
    wr_loss = winrate_loss(best, move)
    annotated["strength_level"] = level
    annotated["selection_reason"] = reason
    if loss is not None:
        annotated["score_loss_vs_best"] = round(loss, 3)
    if wr_loss is not None:
        annotated["winrate_loss_vs_best"] = round(wr_loss, 4)
    return annotated


def choose_by_window(
    best: dict[str, Any],
    moves: list[dict[str, Any]],
    *,
    min_order: int,
    min_score_loss: float,
    max_score_loss: float,
    max_winrate_loss: float,
) -> dict[str, Any] | None:
    for move in moves:
        if int(move.get("order", 999999)) < min_order:
            continue
        loss = score_loss(best, move)
        wr_loss = winrate_loss(best, move)
        if loss is None or wr_loss is None:
            continue
        if min_score_loss <= loss <= max_score_loss and wr_loss <= max_winrate_loss:
            return move
    return None


def choose_fallback(
    best: dict[str, Any],
    moves: list[dict[str, Any]],
    *,
    min_order: int,
    max_score_loss: float,
    max_winrate_loss: float,
) -> dict[str, Any]:
    for move in moves:
        if int(move.get("order", 999999)) < min_order:
            continue
        loss = score_loss(best, move)
        wr_loss = winrate_loss(best, move)
        if loss is None or wr_loss is None:
            return move
        if loss <= max_score_loss and wr_loss <= max_winrate_loss:
            return move
    return best


def recommendations_by_level(candidates: list[dict[str, Any]]) -> dict[str, dict[str, Any] | None]:
    if not candidates:
        return {"beginner": None, "intermediate": None, "advanced": None}

    best = candidates[0]
    intermediate = choose_by_window(
        best,
        candidates,
        min_order=1,
        min_score_loss=0.8,
        max_score_loss=4.0,
        max_winrate_loss=0.12,
    )
    if intermediate is None:
        intermediate = choose_fallback(best, candidates, min_order=1, max_score_loss=5.0, max_winrate_loss=0.15)

    beginner = choose_by_window(
        best,
        candidates,
        min_order=3,
        min_score_loss=3.0,
        max_score_loss=12.0,
        max_winrate_loss=0.25,
    )
    if beginner is None:
        beginner = choose_fallback(best, candidates, min_order=2, max_score_loss=15.0, max_winrate_loss=0.30)

    return {
        "beginner": annotate_strength(
            best,
            beginner,
            "beginner",
            "A playable but intentionally softer candidate, chosen below the top line to reduce playing strength.",
        ),
        "intermediate": annotate_strength(
            best,
            intermediate,
            "intermediate",
            "A solid candidate near the top line, but not necessarily KataGo's strongest move.",
        ),
        "advanced": annotate_strength(
            best,
            best,
            "advanced",
            "KataGo's top candidate by search order.",
        ),
    }


def build_result(args: argparse.Namespace) -> dict[str, Any]:
    side_to_move = normalize_player(args.side_to_move)
    level = normalize_level(args.level)
    rows, recognition = load_board_source(args)
    if len(rows) != args.board_size:
        raise SystemExit(f"Expected {args.board_size} board rows, got {len(rows)}")

    analysis = run_katago_analysis(
        rows,
        side_to_move,
        komi=args.komi,
        visits=args.visits,
        katago=args.katago,
        model=args.model,
        config=args.analysis_config,
        skill_config=args.skill_config,
    )
    move_infos = sorted(analysis.get("moveInfos", []), key=lambda item: item.get("order", 999999))
    candidates = [slim_move_info(move) for move in move_infos[: args.top_candidates]]
    by_level = recommendations_by_level(candidates)
    selected = by_level["advanced"] if level == "all" else by_level[level]
    result = {
        "board_size": len(rows),
        "side_to_move": side_to_move,
        "requested_level": level,
        "rules": "chinese",
        "komi": args.komi,
        "visits_requested": args.visits,
        "board_ascii": rows,
        "recommendation": selected,
        "recommendations_by_level": by_level,
        "candidate_moves": candidates,
        "root_info": analysis.get("rootInfo", {}),
        "katago_warnings": analysis.get("warnings", []),
        "level_policy": {
            "beginner": "Choose a plausible lower-ranked move with a moderate score/winrate loss when available.",
            "intermediate": "Choose a solid near-top candidate with a small score/winrate loss when available.",
            "advanced": "Choose KataGo's top searched candidate.",
        },
    }
    if recognition is not None:
        result["recognition"] = recognition
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Recognize or read a Go position and ask KataGo for the next move.")
    parser.add_argument("source", nargs="?", help="Image path, board_ascii text file, or omitted to read board_ascii from stdin")
    parser.add_argument("--input", choices=["auto", "image", "ascii"], default="auto", help="Input kind, default: auto")
    parser.add_argument("--side-to-move", required=True, help="Side to move: black/B/黑 or white/W/白")
    parser.add_argument("--level", default="advanced", help="Move strength: beginner/初级, intermediate/中级, advanced/高级, or all/全部")
    parser.add_argument("--board-size", type=int, default=19, help="Board size, default: 19")
    parser.add_argument("--komi", type=float, default=7.5, help="Komi, default: 7.5")
    parser.add_argument("--visits", type=int, default=400, help="KataGo visit budget, default: 400")
    parser.add_argument("--top-candidates", type=int, default=20, help="Number of candidate moves to return and consider for level selection")
    parser.add_argument("--warp-size", type=int, default=1200, help="Image recognition warp size")
    parser.add_argument("--corners", help="Manual image board corners as 'x,y x,y x,y x,y'")
    parser.add_argument("--grid-corners", action="store_true", help="Treat --corners as outer grid intersections")
    parser.add_argument("--overlay", type=Path, help="Write a recognition overlay when input is an image")
    parser.add_argument("--katago", default="katago", help="Path to katago executable")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="KataGo model path")
    parser.add_argument("--analysis-config", default=DEFAULT_ANALYSIS_CONFIG, help="KataGo analysis config path")
    parser.add_argument("--skill-config", type=Path, default=DEFAULT_SKILL_CONFIG, help="Project analysis override config")
    args = parser.parse_args()

    if args.visits < 1:
        raise SystemExit("--visits must be at least 1")
    if args.top_candidates < 1:
        raise SystemExit("--top-candidates must be at least 1")
    print(json.dumps(build_result(args), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
