# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "typer",
#     "rich",
#     "pillow",
# ]
# ///

import shutil
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from rich.progress import track
from PIL import Image, UnidentifiedImageError

app = typer.Typer()
console = Console()

# 常见的截图文件扩展名
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.heic', '.webp'}

# 常见的截图命名关键词 (不区分大小写)
SCREENSHOT_KEYWORDS = [
    "screenshot",   # Android / Windows / 通用
    "截屏",         # 中文系统
    "屏幕截图",      # 中文系统
    "screen_shot",  # 部分应用
    "captures",     # 部分系统文件夹名
]

# 常见的手机屏幕宽高比范围 (长边/短边)
# 16:9 = 1.777
# 18:9 = 2.0
# 19.5:9 (iPhone X/11/12/13/14等) = 2.166
# 20:9 (很多Android) = 2.22
# 21:9 (Sony等) = 2.33
# 平板/iPad: 4:3 (1.33)
# 允许一定的误差范围 (+/- 0.05)
SCREENSHOT_RATIO_RANGES = [
    (1.30, 1.36), # 4:3 (iPad/Tablet)
    (1.75, 1.80), # 16:9
    (1.95, 2.40), # 18:9 ~ 21:9 (现代全面屏)
]

def is_screenshot(file_path: Path) -> bool:
    """
    判断是否为截图，采用漏斗式筛选：
    1. 文件名匹配 (最快, 命中即返回 True)
    2. 宽高比检查 + EXIF 排除 (较慢, 用于捞回改名后的截图)
    """
    # 0. 扩展名预检
    if file_path.suffix.lower() not in IMAGE_EXTENSIONS:
        return False
    
    filename = file_path.name.lower()
    
    # 1. 快速层：文件名匹配
    for keyword in SCREENSHOT_KEYWORDS:
        if keyword in filename:
            return True
            
    # 2. 验证层：图像特征分析 (需要读取文件)
    try:
        with Image.open(file_path) as img:
            # A. EXIF 排除法
            # 如果包含相机特定的 EXIF 信息 (如光圈 FNumber, 曝光时间 ExposureTime, ISO 等)
            # 则极大概率是照片，直接排除
            exif = img._getexif()
            if exif:
                # 33434: ExposureTime, 33437: FNumber, 34855: ISOSpeedRatings
                # 36867: DateTimeOriginal (截图可能有，照片必有)
                # 271: Make (相机厂商, 截图有时也会带设备名，不能单以此判断)
                photo_tags = {33434, 33437, 34855}
                for tag in photo_tags:
                    if tag in exif:
                        return False # 肯定是照片

            # B. 分辨率比例检查
            w, h = img.size
            if w == 0 or h == 0: return False
            
            # 计算长宽比
            long_side = max(w, h)
            short_side = min(w, h)
            ratio = long_side / short_side
            
            for (min_r, max_r) in SCREENSHOT_RATIO_RANGES:
                if min_r <= ratio <= max_r:
                    return True
                    
    except (UnidentifiedImageError, OSError):
        # 图片损坏或无法读取，跳过
        return False
    except Exception:
        return False
    
    return False

@app.command()
def main(
    folder: str = typer.Argument(..., help="要搜索的根目录路径"),
    copy_to: Optional[str] = typer.Option(None, "--copy-to", "-c", help="[可选] 将找到的截图复制到此目录"),
    move_to: Optional[str] = typer.Option(None, "--move-to", "-m", help="[可选] 将找到的截图移动到此目录 (慎用)"),
):
    """
    递归查找文件夹内的手机截图。
    
    策略：
    1. 优先匹配文件名关键词 (screenshot, 截屏等)。
    2. 其次分析图片比例 (匹配常见手机/平板比例) 并排除带有相机EXIF(光圈/ISO)的照片。
    """
    root_dir = Path(folder)
    
    if not root_dir.exists():
        console.print(f"[bold red]错误:[/bold red] 目录 '{folder}' 不存在")
        raise typer.Exit(code=1)

    console.print(f"[bold blue]正在扫描目录:[/bold blue] {root_dir.resolve()}")
    
    found_files = []
    
    # rglob('*') 会递归遍历所有子文件夹
    all_files = list(root_dir.rglob("*"))
    
    # 过滤出文件，减少进度条数量
    image_files = [f for f in all_files if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS]
    
    for file_path in track(image_files, description="智能识别中..."):
        if is_screenshot(file_path):
            found_files.append(file_path)

    # --- 结果展示 ---
    if not found_files:
        console.print("[yellow]未找到符合特征的截图文件。[/yellow]")
        return

    table = Table(title=f"找到 {len(found_files)} 张截图")
    table.add_column("文件名", style="green")
    table.add_column("路径 (相对)", style="dim")
    table.add_column("识别方式", style="cyan") 

    for f in found_files:
        try:
            rel_path = f.relative_to(root_dir)
        except:
            rel_path = f
            
        # 简单标记是文件名命中还是特征命中 (为了展示效果，这里稍微重复了一点逻辑，实际使用可忽略)
        is_name_match = any(k in f.name.lower() for k in SCREENSHOT_KEYWORDS)
        method = "文件名" if is_name_match else "图像特征"
        
        table.add_row(f.name, str(rel_path.parent), method)

    console.print(table)

    # --- 复制/移动 操作 ---
    dest_dir = None
    action_type = None # 'copy' or 'move'

    if copy_to:
        dest_dir = Path(copy_to)
        action_type = 'copy'
    elif move_to:
        dest_dir = Path(move_to)
        action_type = 'move'

    if dest_dir:
        dest_dir.mkdir(parents=True, exist_ok=True)
        console.print(f"\n[bold]正在执行 {action_type} 到:[/bold] {dest_dir}")
        
        for f in found_files:
            try:
                target = dest_dir / f.name
                if target.exists():
                    console.print(f"[yellow]跳过 (已存在):[/yellow] {f.name}")
                    continue
                
                if action_type == 'copy':
                    shutil.copy2(f, target)
                else:
                    shutil.move(f, target)
            except Exception as e:
                console.print(f"[red]操作失败 {f.name}: {e}[/red]")
        
        console.print(f"[bold green]完成！[/bold green]")

if __name__ == "__main__":
    app()