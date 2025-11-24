"""
CLI for handwriting detection and OCR routing.

Usage:
    arxiv2rm-detect <image>                    # Detect single image
    arxiv2rm-detect <dir>/*.png                # Batch detect
    arxiv2rm-detect --help                     # Show help
"""

import json
import sys
from pathlib import Path

import click

from .handwriting_detector import HandwritingDetector


@click.group()
@click.version_option()
def main():
    """ArXiv2RM Handwriting Detection CLI."""
    pass


@main.command()
@click.argument("images", nargs=-1, type=click.Path(exists=True))
@click.option("--confidence-threshold", default=0.85, help="Confidence threshold (0-1)")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def detect(images: tuple, confidence_threshold: float, output_json: bool, verbose: bool):
    """Detect handwritten vs printed text in images."""

    if not images:
        click.echo("Error: No images specified", err=True)
        click.echo("Usage: arxiv2rm-detect detect <image1> [image2 ...]")
        sys.exit(1)

    detector = HandwritingDetector(confidence_threshold=confidence_threshold)
    results = []

    for img_path in images:
        img_path = Path(img_path)

        if not img_path.exists():
            click.echo(f"Warning: {img_path} does not exist", err=True)
            continue

        result = detector.detect(img_path)

        results.append(
            {
                "file": str(img_path),
                "is_handwritten": result["is_handwritten"],
                "confidence": result["confidence"],
                "recommendation": result["recommendation"],
                "reasons": result["reasons"] if verbose else None,
                "scores": result["scores"] if verbose else None,
            }
        )

        if not output_json:
            status = "HANDWRITTEN" if result["is_handwritten"] else "PRINTED"
            color = "yellow" if result["is_handwritten"] else "green"

            click.echo(
                f"{click.style(img_path.name, bold=True)}: "
                f"{click.style(status, fg=color)} "
                f"({result['confidence']:.0%}) "
                f"→ {click.style(result['recommendation'].upper(), fg='cyan')}"
            )

            if verbose:
                for reason in result["reasons"][:3]:
                    click.echo(f"  • {reason}")

    if output_json:
        click.echo(json.dumps(results, indent=2))


@main.command()
@click.argument("images", nargs=-1, type=click.Path(exists=True))
@click.option("--confidence-threshold", default=0.85, help="Confidence threshold")
def estimate(images: tuple, confidence_threshold: float):
    """Estimate OCR costs for batch of images."""

    if not images:
        click.echo("Error: No images specified", err=True)
        sys.exit(1)

    detector = HandwritingDetector(confidence_threshold=confidence_threshold)

    groq_count = 0
    local_count = 0
    total_size_mb = 0

    for img_path in images:
        img_path = Path(img_path)

        if not img_path.exists():
            continue

        result = detector.detect(img_path)
        file_size_mb = img_path.stat().st_size / (1024 * 1024)
        total_size_mb += file_size_mb

        if result["is_handwritten"]:
            groq_count += 1
        else:
            local_count += 1

    total = groq_count + local_count
    groq_cost = groq_count * 0.04  # ~$0.04 per handwritten page
    potential_cost = total * 0.04  # If using Groq for all

    click.echo("\n" + "=" * 60)
    click.echo("  OCR COST ESTIMATE")
    click.echo("=" * 60)
    click.echo(f"\nTotal images:     {total}")
    click.echo(f"Total size:       {total_size_mb:.1f} MB")
    click.echo()

    groq_pct = groq_count / total * 100
    local_pct = local_count / total * 100
    click.echo("Routing decision:")
    click.echo(f"  → Groq API:     {groq_count} images ({groq_pct:.0f}%)")
    click.echo(f"  → Local OCR:    {local_count} images ({local_pct:.0f}%)")

    click.echo("\nCost breakdown:")
    click.echo(f"  Groq pages:     {groq_count} × $0.04 = ${groq_cost:.2f}")
    click.echo(f"  Local pages:    {local_count} × $0    = $0.00")
    total_label = click.style("Total cost:", bold=True)
    click.echo(f"  {total_label}     ${groq_cost:.2f}")
    click.echo()

    if groq_count < total:
        savings = potential_cost - groq_cost
        if potential_cost > 0:
            savings_pct = (1 - groq_cost / potential_cost) * 100
        else:
            savings_pct = 0
        click.echo(f"  vs Groq-only:   ${potential_cost:.2f}")
        savings_label = click.style("Savings:", bold=True, fg="green")
        click.echo(f"  {savings_label}        ${savings:.2f} ({savings_pct:.0f}%)")
        click.echo()

    click.echo("=" * 60 + "\n")


@main.command()
@click.argument("image", type=click.Path(exists=True))
@click.option("--deepseek-confidence", type=float, help="DeepSeek OCR confidence (0-1)")
@click.option("--deepseek-text", type=str, help="DeepSeek OCR extracted text")
def analyze(image: str, deepseek_confidence: float, deepseek_text: str):
    """Detailed analysis of single image with optional OCR results."""

    img_path = Path(image)
    detector = HandwritingDetector()

    click.echo("\n" + "=" * 60)
    click.echo("  HANDWRITING DETECTION ANALYSIS")
    click.echo("=" * 60 + "\n")
    click.echo(f"File: {img_path.name}")
    click.echo(f"Size: {img_path.stat().st_size / 1024:.1f} KB")

    result = detector.detect(img_path, deepseek_confidence, deepseek_text)

    click.echo(f"\n{click.style('Detection Result:', bold=True)}")
    is_hw = result["is_handwritten"]
    type_label = "HANDWRITTEN" if is_hw else "PRINTED"
    type_color = "yellow" if is_hw else "green"
    type_styled = click.style(type_label, fg=type_color)
    click.echo(f"  Type:           {type_styled}")
    click.echo(f"  Confidence:     {result['confidence']:.2%}")
    rec_label = click.style(result["recommendation"].upper(), fg="cyan")
    click.echo(f"  Recommendation: Use {rec_label} OCR")

    click.echo(f"\n{click.style('Detection Scores:', bold=True)}")
    for key, value in result["scores"].items():
        if value is not None:
            label = key.replace("_", " ").title()
            click.echo(f"  {label:20s} {value:.2f}")

    click.echo(f"\n{click.style('Detection Reasons:', bold=True)}")
    for i, reason in enumerate(result["reasons"], 1):
        click.echo(f"  {i}. {reason}")

    click.echo("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    main()
