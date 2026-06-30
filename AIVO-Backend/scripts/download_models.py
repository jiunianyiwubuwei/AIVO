"""下载 AI 模型到项目本地目录

运行方式:
    python scripts/download_models.py

模型将下载到:
    models/whisper/     - Whisper 语音模型
    models/mediapipe/  - MediaPipe 人脸模型
"""

import os
import sys
from pathlib import Path

# 设置编码
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def download_whisper_models():
    """下载 Whisper 模型"""
    import whisper

    models_dir = project_root / "models" / "whisper"
    models_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("下载 Whisper 语音识别模型")
    print("=" * 60)
    print(f"目标目录: {models_dir}")
    print()
    print("可用模型:")
    print("  tiny   - ~39 MB  (最快, 精度最低)")
    print("  base   - ~140 MB (推荐)")
    print("  small  - ~466 MB")
    print("  medium - ~1.5 GB")
    print("  large  - ~2.9 GB")
    print()

    # 下载 base 模型（默认）
    model_name = "base"
    print(f"正在下载 '{model_name}' 模型...")

    try:
        model = whisper.load_model(model_name, download_root=str(models_dir))
        print(f"✓ Whisper {model_name} 模型下载成功!")

        # 检查已下载的模型
        downloaded = list(models_dir.glob("*.pt"))
        print(f"\n已下载的模型文件:")
        for f in downloaded:
            size_mb = f.stat().st_size / 1024 / 1024
            print(f"  {f.name} ({size_mb:.1f} MB)")

        return True
    except Exception as e:
        print(f"✗ Whisper 模型下载失败: {e}")
        return False


def download_mediapipe_models():
    """下载 MediaPipe 模型"""
    import urllib.request

    models_dir = project_root / "models" / "mediapipe"
    models_dir.mkdir(parents=True, exist_ok=True)

    print()
    print("=" * 60)
    print("下载 MediaPipe 人脸检测模型")
    print("=" * 60)

    # MediaPipe FaceLandmarker 模型 URL
    model_url = (
        "https://storage.googleapis.com/mediapipe-models/"
        "face_landmarker/face_landmarker/float16/1/"
        "face_landmarker.task"
    )

    model_path = models_dir / "face_landmarker.task"

    if model_path.exists():
        size_mb = model_path.stat().st_size / 1024 / 1024
        print(f"模型已存在: {model_path} ({size_mb:.1f} MB)")
        print("跳过下载，如需重新下载请删除文件。")
        return True

    print(f"目标路径: {model_path}")
    print(f"下载链接: {model_url}")
    print()
    print("正在下载 MediaPipe FaceLandmarker 模型...")
    print("(首次下载可能需要几分钟，取决于网络速度)")

    try:
        # 下载文件
        urllib.request.urlretrieve(model_url, str(model_path))

        size_mb = model_path.stat().st_size / 1024 / 1024
        print(f"✓ MediaPipe 模型下载成功!")
        print(f"  文件: {model_path.name}")
        print(f"  大小: {size_mb:.1f} MB")

        return True
    except Exception as e:
        print(f"✗ MediaPipe 模型下载失败: {e}")
        if model_path.exists():
            model_path.unlink()
        return False


def main():
    print()
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "AI 模型下载脚本" + " " * 26 + "║")
    print("║" + " " * 15 + "AI-Meeting 项目" + " " * 26 + "║")
    print("╚" + "=" * 58 + "╝")
    print()

    results = {}

    # 下载 Whisper
    results["whisper"] = download_whisper_models()

    # 下载 MediaPipe
    results["mediapipe"] = download_mediapipe_models()

    # 总结
    print()
    print("=" * 60)
    print("下载完成!")
    print("=" * 60)

    all_success = all(results.values())
    if all_success:
        print("✓ 所有模型下载成功!")
        print()
        print("模型目录结构:")
        print("  models/")
        print("  ├── whisper/")
        print("  │   └── base.pt          (Whisper base 模型)")
        print("  └── mediapipe/")
        print("      └── face_landmarker.task  (MediaPipe 人脸模型)")
        return 0
    else:
        print("⚠ 部分模型下载失败，请检查网络连接后重试。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
