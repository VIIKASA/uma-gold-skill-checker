import sys
from pathlib import Path


def main() -> None:
    bundle_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    app_path = bundle_dir / "app.py"
    if not app_path.is_file():
        raise FileNotFoundError(f"Streamlit 앱 파일을 찾을 수 없습니다: {app_path}")

    from streamlit.web import cli as stcli

    sys.argv = [
        "streamlit",
        "run",
        str(app_path),
        "--global.developmentMode=false",
        "--server.headless=false",
        "--server.fileWatcherType=none",
        "--browser.gatherUsageStats=false",
    ]
    stcli.main()


if __name__ == "__main__":
    main()