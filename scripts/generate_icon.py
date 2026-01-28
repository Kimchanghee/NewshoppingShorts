#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate program icons for Shopping Shorts Maker
Creates PNG and ICO icons with shopping bag + play button design
"""
import os
import sys
import math

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("Pillow is required. Install with: pip install pillow")
    sys.exit(1)


def draw_rounded_rect(draw: ImageDraw.Draw, xy: tuple, radius: int, fill: str) -> None:
    """Draw a rounded rectangle."""
    x1, y1, x2, y2 = xy

    # Draw main rectangle
    draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
    draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)

    # Draw corners
    draw.ellipse([x1, y1, x1 + radius * 2, y1 + radius * 2], fill=fill)
    draw.ellipse([x2 - radius * 2, y1, x2, y1 + radius * 2], fill=fill)
    draw.ellipse([x1, y2 - radius * 2, x1 + radius * 2, y2], fill=fill)
    draw.ellipse([x2 - radius * 2, y2 - radius * 2, x2, y2], fill=fill)


def generate_app_icon(size: int = 256) -> Image.Image:
    """
    Generate shopping shorts maker icon.

    Design: Indigo rounded square background with shopping bag silhouette
    and play button overlay.

    Args:
        size: Icon size in pixels (square)

    Returns:
        PIL Image object
    """
    # Create transparent base
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Colors
    primary = "#6366F1"  # Indigo
    white = "#FFFFFF"
    accent = "#4F46E5"  # Darker indigo for play button

    # Convert hex to RGB
    def hex_to_rgb(hex_color: str) -> tuple:
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    primary_rgb = hex_to_rgb(primary)
    white_rgb = hex_to_rgb(white)
    accent_rgb = hex_to_rgb(accent)

    # Draw rounded rectangle background
    padding = int(size * 0.08)
    corner_radius = int(size * 0.18)
    draw_rounded_rect(
        draw,
        (padding, padding, size - padding, size - padding),
        corner_radius,
        primary_rgb
    )

    # Shopping bag dimensions
    bag_width = int(size * 0.45)
    bag_height = int(size * 0.50)
    bag_left = (size - bag_width) // 2
    bag_top = int(size * 0.30)
    bag_right = bag_left + bag_width
    bag_bottom = bag_top + bag_height
    bag_radius = int(size * 0.04)

    # Draw shopping bag body (rounded rectangle)
    draw_rounded_rect(
        draw,
        (bag_left, bag_top, bag_right, bag_bottom),
        bag_radius,
        white_rgb
    )

    # Draw shopping bag handle (arc using lines)
    handle_width = int(bag_width * 0.5)
    handle_height = int(size * 0.12)
    handle_left = bag_left + (bag_width - handle_width) // 2
    handle_right = handle_left + handle_width
    handle_top = bag_top - handle_height
    handle_thickness = int(size * 0.035)

    # Draw handle as a series of ellipse segments (outer and inner)
    # Outer handle
    draw.arc(
        [handle_left, handle_top, handle_right, bag_top + handle_height],
        start=180,
        end=0,
        fill=white_rgb,
        width=handle_thickness
    )

    # Draw play button (triangle) in center of bag
    play_center_x = size // 2 + int(size * 0.02)  # Slightly right offset for visual balance
    play_center_y = bag_top + bag_height // 2
    play_size = int(size * 0.10)

    # Triangle points (pointing right)
    triangle = [
        (play_center_x - int(play_size * 0.6), play_center_y - play_size),
        (play_center_x - int(play_size * 0.6), play_center_y + play_size),
        (play_center_x + int(play_size * 0.9), play_center_y)
    ]
    draw.polygon(triangle, fill=accent_rgb)

    return img


def save_icons(output_dir: str = None) -> dict:
    """
    Save icons in multiple sizes and formats.

    Args:
        output_dir: Output directory path (default: resource folder)

    Returns:
        Dict with paths of generated files
    """
    if output_dir is None:
        # Default to resource folder in project root
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        output_dir = os.path.join(project_root, "resource")

    os.makedirs(output_dir, exist_ok=True)

    generated_files = {}

    # Generate main icon (256x256)
    icon_256 = generate_app_icon(256)
    main_path = os.path.join(output_dir, "mainTrayIcon.png")
    icon_256.save(main_path, "PNG")
    generated_files['main'] = main_path
    print(f"Generated: {main_path}")

    # Generate tray icon (64x64)
    icon_64 = icon_256.resize((64, 64), Image.Resampling.LANCZOS)
    tray_path = os.path.join(output_dir, "trayIcon.png")
    icon_64.save(tray_path, "PNG")
    generated_files['tray'] = tray_path
    print(f"Generated: {tray_path}")

    # Generate ICO file with multiple sizes (Windows)
    ico_path = os.path.join(output_dir, "app_icon.ico")
    try:
        # Create icons at different sizes
        icon_sizes = [
            (256, 256),
            (128, 128),
            (64, 64),
            (48, 48),
            (32, 32),
            (16, 16)
        ]

        icons = []
        for w, h in icon_sizes:
            resized = icon_256.resize((w, h), Image.Resampling.LANCZOS)
            icons.append(resized)

        # Save ICO with all sizes
        icons[0].save(
            ico_path,
            format='ICO',
            sizes=icon_sizes,
            append_images=icons[1:]
        )
        generated_files['ico'] = ico_path
        print(f"Generated: {ico_path}")
    except Exception as e:
        print(f"ICO generation failed (non-critical): {e}")

    return generated_files


def main():
    """Main entry point."""
    print("=" * 50)
    print("  Shopping Shorts Maker Icon Generator")
    print("=" * 50)
    print()

    files = save_icons()

    print()
    print("=" * 50)
    print(f"  Generated {len(files)} icon file(s)")
    print("=" * 50)

    return 0


if __name__ == "__main__":
    sys.exit(main())
