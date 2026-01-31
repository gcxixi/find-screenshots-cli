import sys
import os
import pytest
from pathlib import Path
from PIL import Image

# 将根目录添加到路径以便导入 find_screenshots
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from find_screenshots import is_screenshot

TEST_ASSETS_DIR = Path("tests")
BASE_IMAGE = TEST_ASSETS_DIR / "base_ui.png"

@pytest.fixture(scope="module")
def prepared_images():
    """
    基于生成的基准图，制作各种测试用例图片。
    """
    if not BASE_IMAGE.exists():
        pytest.fail(f"基准测试图片 {BASE_IMAGE} 不存在，请先生成。")

    created_files = []
    
    with Image.open(BASE_IMAGE) as img:
        # Case 1: 文件名匹配 (Filename Match)
        # 内容无所谓 (原图 1:1)，但名字包含 "Screenshot"
        path_1 = TEST_ASSETS_DIR / "Screenshot_20260130.png"
        img.save(path_1)
        created_files.append((path_1, True, "文件名匹配"))

        # Case 2: 特征匹配 (Feature Match - Ratio)
        # 名字随机，但比例修改为手机比例 (例如 9:19.5 ≈ 0.46)
        # 1024x1024 -> Crop to 472x1024 (Ratio ~2.16, typical iPhone)
        path_2 = TEST_ASSETS_DIR / "img_random_name_001.png"
        box = (0, 0, 472, 1024)
        img_cropped = img.crop(box)
        img_cropped.save(path_2)
        created_files.append((path_2, True, "特征匹配(宽高比)"))

        # Case 3: 非截图 (Invalid Ratio)
        # 名字随机，比例 1:1 (不符合手机特征)
        path_3 = TEST_ASSETS_DIR / "img_random_name_002.png"
        img.save(path_3) # Save original 1:1
        created_files.append((path_3, False, "非截图(比例不符)"))

        # Case 4: 非图片文件
        path_4 = TEST_ASSETS_DIR / "not_an_image.txt"
        path_4.write_text("This is text")
        created_files.append((path_4, False, "非图片文件"))

    yield created_files

    # Cleanup
    for p, _, _ in created_files:
        if p.exists():
            p.unlink()

def test_is_screenshot(prepared_images):
    print("\n---------------- 测试开始 ----------------")
    for file_path, expected_result, description in prepared_images:
        result = is_screenshot(file_path)
        print(f"测试文件: {file_path.name:<25} | 预期: {str(expected_result):<5} | 实际: {str(result):<5} | 说明: {description}")
        assert result == expected_result, f"Failed on {description}: {file_path}"
    print("---------------- 测试通过 ----------------\n")
