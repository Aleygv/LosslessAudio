"""
Generates high-resolution application icon and .ico file.
"""
import os
from PIL import Image, ImageDraw, ImageFont

def generate_app_icon():
    size = (512, 512)
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Rounded Dark Background with Gradient / Glowing Border
    # Draw glowing rounded rectangle
    margin = 32
    rect = [margin, margin, size[0] - margin, size[1] - margin]
    
    # Outer glow
    for i in range(12, 0, -2):
        alpha = int(25 * (12 - i) / 12)
        glow_rect = [margin - i, margin - i, size[0] - margin + i, size[1] - margin + i]
        draw.rounded_rectangle(glow_rect, radius=90 + i, fill=(99, 102, 241, alpha))

    # Main Card Base (#181824)
    draw.rounded_rectangle(rect, radius=90, fill=(24, 24, 36, 255), outline=(99, 102, 241, 255), width=6)

    # 2. Modern Gradient / Neon Waveform & Note
    center_x, center_y = size[0] // 2, size[1] // 2

    # Draw stylish Headphones / Sound waves
    # Headphone arch
    arch_box = [center_x - 140, center_y - 140, center_x + 140, center_y + 140]
    draw.arc(arch_box, start=180, end=0, fill=(16, 185, 129, 255), width=16)

    # Ear cups
    # Left cup
    draw.rounded_rectangle([center_x - 160, center_y - 30, center_x - 120, center_y + 80], radius=16, fill=(99, 102, 241, 255))
    # Right cup
    draw.rounded_rectangle([center_x + 120, center_y - 30, center_x + 160, center_y + 80], radius=16, fill=(99, 102, 241, 255))

    # Center Musical Note with gradient fill
    # Note head 1
    draw.ellipse([center_x - 60, center_y + 40, center_x - 10, center_y + 85], fill=(6, 182, 212, 255))
    # Note head 2
    draw.ellipse([center_x + 15, center_y + 20, center_x + 65, center_y + 65], fill=(6, 182, 212, 255))
    # Note stems
    draw.rectangle([center_x - 20, center_y - 60, center_x - 10, center_y + 60], fill=(6, 182, 212, 255))
    draw.rectangle([center_x + 55, center_y - 80, center_x + 65, center_y + 40], fill=(6, 182, 212, 255))
    # Beam connecting stems
    draw.polygon([
        (center_x - 20, center_y - 45),
        (center_x + 65, center_y - 65),
        (center_x + 65, center_y - 85),
        (center_x - 20, center_y - 65),
    ], fill=(16, 185, 129, 255))

    # 3. Hi-Res Badge
    badge_rect = [center_x - 70, size[1] - margin - 65, center_x + 70, size[1] - margin - 25]
    draw.rounded_rectangle(badge_rect, radius=10, fill=(245, 158, 11, 255))
    
    # Save PNG and ICO
    assets_dir = os.path.join(os.path.dirname(__file__), "assets")
    os.makedirs(assets_dir, exist_ok=True)
    
    png_path = os.path.join(assets_dir, "app_icon.png")
    ico_path = os.path.join(assets_dir, "app_icon.ico")
    
    img.save(png_path, format="PNG")
    
    # Save multi-size icon
    icon_sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    img.save(ico_path, format="ICO", sizes=icon_sizes)
    
    print(f"Generated icons:\n  {png_path}\n  {ico_path}")

if __name__ == "__main__":
    generate_app_icon()
