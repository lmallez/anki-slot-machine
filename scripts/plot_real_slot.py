#!/usr/bin/env python3
from __future__ import annotations

import argparse
from decimal import Decimal
from pathlib import Path

try:
    import matplotlib

    matplotlib.use("Agg")

    import matplotlib.pyplot as plt
except ModuleNotFoundError as exc:
    raise SystemExit(
        "matplotlib is required for this script. Install it with "
        "`./.venv/bin/python -m pip install matplotlib` and run again."
    ) from exc

from evaluate_real_slot import build_stats, merged_inputs


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_PATH = ROOT / "dist" / "real_slot_profile.png"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot a real slot distribution from face counts and gains.",
    )
    parser.add_argument(
        "--profile",
        type=Path,
        default=ROOT / "src" / "anki_slot_machine" / "slot_profiles" / "base.json",
        help="Optional JSON profile with faces and multipliers.",
    )
    parser.add_argument(
        "--face",
        action="append",
        default=[],
        metavar="SLOT_N=COUNT",
        help="Override one face count. Can be repeated.",
    )
    parser.add_argument(
        "--pair",
        action="append",
        default=[],
        metavar="SLOT_N=MULTIPLIER",
        help="Override one exact-pair multiplier. Can be repeated.",
    )
    parser.add_argument(
        "--triple",
        action="append",
        default=[],
        metavar="SLOT_N=MULTIPLIER",
        help="Override one triple multiplier. Can be repeated.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Output PNG path.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    name, faces, pair, triple = merged_inputs(args)
    stats, total_pair, total_triple, no_match, ev = build_stats(faces, pair, triple)

    args.output.parent.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(2, 2, figsize=(16, 11), constrained_layout=True)
    fig.patch.set_facecolor("#101114")
    for axis in axes.flat:
        axis.set_facecolor("#17191d")
        axis.tick_params(colors="#e8e6e3")
        for spine in axis.spines.values():
            spine.set_color("#3f4650")

    probability_axis = axes[0, 0]
    scatter_axis = axes[0, 1]
    contribution_axis = axes[1, 0]
    rarity_axis = axes[1, 1]

    labels = [entry.symbol for entry in stats]
    x = list(range(len(labels)))
    pair_x = [float(entry.exact_pair_probability * Decimal("100")) for entry in stats]
    pair_y = [float(entry.pair_multiplier) for entry in stats]
    triple_x = [float(entry.triple_probability * Decimal("100")) for entry in stats]
    triple_y = [float(entry.triple_multiplier) for entry in stats]
    pair_ev = [float(entry.pair_ev) for entry in stats]
    triple_ev = [float(entry.triple_ev) for entry in stats]
    reel_prob = [float(entry.reel_probability * Decimal("100")) for entry in stats]
    width = 0.28

    probability_axis.bar(
        [i - width for i in x],
        reel_prob,
        width,
        color="#6fb1fc",
        label="Single reel %",
    )
    probability_axis.bar(
        x,
        pair_x,
        width,
        color="#f6c85f",
        label="Exact pair %",
    )
    probability_axis.bar(
        [i + width for i in x],
        triple_x,
        width,
        color="#f08a5d",
        label="Triple %",
    )
    probability_axis.set_xticks(x, labels)
    probability_axis.set_ylabel("Probability (%)", color="#e8e6e3")
    probability_axis.set_title("Probability Ladder", color="#ffffff")
    probability_axis.grid(axis="y", color="#30353d", alpha=0.35)
    probability_axis.legend(
        facecolor="#17191d",
        edgecolor="#3f4650",
        labelcolor="#e8e6e3",
    )
    for idx, value in enumerate(pair_x):
        probability_axis.text(
            x[idx],
            value + max(0.12, value * 0.015),
            f"{value:.2f}%",
            ha="center",
            va="bottom",
            fontsize=8,
            color="#f6c85f",
        )

    scatter_axis.scatter(pair_x, pair_y, s=110, color="#f6c85f", label="Exact pair")
    scatter_axis.scatter(triple_x, triple_y, s=110, color="#f08a5d", label="Triple")
    scatter_axis.scatter(
        [float(no_match * Decimal("100"))],
        [0.0],
        s=130,
        color="#6c757d",
        label="No match",
    )

    for entry in stats:
        scatter_axis.annotate(
            f"{entry.symbol} pair",
            (float(entry.exact_pair_probability * Decimal("100")), float(entry.pair_multiplier)),
            textcoords="offset points",
            xytext=(6, 6),
            color="#f6c85f",
            fontsize=8,
        )
        scatter_axis.annotate(
            f"{entry.symbol} triple",
            (float(entry.triple_probability * Decimal("100")), float(entry.triple_multiplier)),
            textcoords="offset points",
            xytext=(6, 6),
            color="#f08a5d",
            fontsize=8,
        )

    scatter_axis.annotate(
        "NO_MATCH",
        (float(no_match * Decimal("100")), 0.0),
        textcoords="offset points",
        xytext=(6, 6),
        color="#c9ced6",
        fontsize=8,
    )

    scatter_axis.set_xlabel("Probability (%)", color="#e8e6e3")
    scatter_axis.set_ylabel("Reward multiplier", color="#e8e6e3")
    scatter_axis.set_title("Probability vs Reward", color="#ffffff")
    scatter_axis.grid(color="#30353d", alpha=0.35)
    scatter_axis.legend(
        facecolor="#17191d",
        edgecolor="#3f4650",
        labelcolor="#e8e6e3",
    )

    contribution_axis.bar(
        [i - width / 2 for i in x],
        pair_ev,
        width,
        color="#f6c85f",
        label="Pair EV contribution",
    )
    contribution_axis.bar(
        [i + width / 2 for i in x],
        triple_ev,
        width,
        color="#f08a5d",
        label="Triple EV contribution",
    )
    contribution_axis.set_xticks(x, labels)
    contribution_axis.set_ylabel("EV contribution", color="#e8e6e3")
    contribution_axis.set_title("Expected Value Contribution", color="#ffffff")
    contribution_axis.grid(axis="y", color="#30353d", alpha=0.35)
    contribution_axis.legend(
        facecolor="#17191d",
        edgecolor="#3f4650",
        labelcolor="#e8e6e3",
    )
    for idx, value in enumerate(pair_ev):
        contribution_axis.text(
            x[idx] - width / 2,
            value + max(0.002, value * 0.04),
            f"{value:.3f}",
            ha="center",
            va="bottom",
            fontsize=8,
            color="#f6c85f",
        )

    rarity_axis.plot(
        reel_prob,
        pair_y,
        marker="o",
        linewidth=2.0,
        color="#f6c85f",
        label="Pair reward curve",
    )
    rarity_axis.plot(
        reel_prob,
        triple_y,
        marker="o",
        linewidth=2.0,
        color="#f08a5d",
        label="Triple reward curve",
    )
    rarity_axis.set_xlabel("Single reel probability (%)", color="#e8e6e3")
    rarity_axis.set_ylabel("Reward multiplier", color="#e8e6e3")
    rarity_axis.set_title("Rarity vs Reward Curve", color="#ffffff")
    rarity_axis.grid(color="#30353d", alpha=0.35)
    rarity_axis.invert_xaxis()
    rarity_axis.legend(
        facecolor="#17191d",
        edgecolor="#3f4650",
        labelcolor="#e8e6e3",
    )
    for entry in stats:
        rarity_axis.annotate(
            entry.symbol,
            (float(entry.reel_probability * Decimal("100")), float(entry.triple_multiplier)),
            textcoords="offset points",
            xytext=(5, 5),
            color="#e8e6e3",
            fontsize=8,
        )

    fig.suptitle(
        f"{name} | EV x{float(ev):.4f} | no match {float(no_match * Decimal('100')):.2f}% | "
        f"pair {float(total_pair * Decimal('100')):.2f}% | triple {float(total_triple * Decimal('100')):.2f}%",
        color="#c9ced6",
        fontsize=12,
    )

    fig.savefig(args.output, dpi=180, bbox_inches="tight")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
