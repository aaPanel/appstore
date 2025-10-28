import os
import json
import shutil
import zipfile
import argparse
from datetime import datetime
from pathlib import Path


def ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log(msg: str):
    print(f"{ts()} {msg}")

def warn(msg: str):
    print(f"{ts()} ⚠️ {msg}")

def err(msg: str):
    print(f"{ts()} ❌ {msg}")

def ok(msg: str):
    print(f"{ts()} ✅ {msg}")

def format_json_mixed(obj, indent: int = 2):
    """
    混合格式化 JSON：
    - 外层对象：正常缩进 (indent)
    - 数组中的 dict 对象：压缩为一行，但整体缩进 (indent * 2)
    说明：用于 app.json / apps.json 读写，兼顾可读性与体积。
    """
    space = ' ' * indent
    inner_space = ' ' * (indent * 2)

    lines = ['{']
    items = []

    for key, value in obj.items():
        key_str = json.dumps(key, ensure_ascii=False)

        if isinstance(value, list):
            array_lines = []
            for item in value:
                if isinstance(item, dict):
                    compact = json.dumps(item, ensure_ascii=False, separators=(',', ':'))
                else:
                    compact = json.dumps(item, ensure_ascii=False)
                array_lines.append(inner_space + compact)
            value_str = '[\n' + ',\n'.join(array_lines) + '\n' + space + ']'
        elif isinstance(value, dict):
            value_str = json.dumps(value, ensure_ascii=False) if value else '{}'
        else:
            value_str = json.dumps(value, ensure_ascii=False)

        items.append(f"{space}{key_str}: {value_str}")

    lines.append(',\n'.join(items))
    lines.append('}')
    return '\n'.join(lines)

def zip_directory(source_directory: Path, zip_file_path: Path, archive_root: Path):
    zip_file_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zip_archive:
        for current_root, _, file_names in os.walk(source_directory):
            for file_name in file_names:
                file_path = Path(current_root) / file_name
                archive_name = file_path.relative_to(archive_root)
                zip_archive.write(file_path, arcname=archive_name)

def process_app_icon(app_folder: Path, icon_target_directory: Path, debug: bool, failures: list[str]) -> str | None:
    """处理单个应用的图标复制并打包图标目录。返回状态: 'ok'/'fail'/None(跳过)。"""
    app_name = app_folder.name
    status: str | None = None
    try:
        if 'gpu' not in app_name:
            icon_filename = f"ico-dkapp_{app_name}.png"
            icon_source_path = app_folder / icon_filename
            if not icon_source_path.exists() or not icon_source_path.is_file():
                status = 'fail'
                failures.append(f"{app_name}: 缺少图标 {icon_source_path}")
            else:
                destination_path = icon_target_directory / icon_filename
                shutil.copy2(icon_source_path, destination_path)
                status = 'ok'
                if debug:
                    ok(f"已复制图标: {icon_source_path} -> {destination_path}")
    except Exception as error:
        status = 'fail'
        failures.append(f"{app_name}: 复制图标失败 - {error}")
    return status

def process_all_icons(apps_dir: Path, icon_target_directory: Path, debug: bool, failures: list[str]):
    """
    批量处理所有应用图标：
    - 遍历 apps 目录下的所有应用文件夹
    - 复制每个应用的图标到 pkg/dkapp_ico
    - 最后统一打包 zip（无论是否传入 selected_apps，都处理全部应用图标）
    """
    pkg_dir = icon_target_directory.parent
    icon_target_directory.mkdir(parents=True, exist_ok=True)

    app_dirs = sorted([p for p in apps_dir.iterdir() if p.is_dir()], key=lambda p: p.name.lower())
    copied = 0
    for app_folder in app_dirs:
        status = process_app_icon(app_folder, icon_target_directory, debug, failures)
        if status == 'ok':
            copied += 1

    # 统一打包图标目录
    if copied > 0:
        if debug:
            log("开始压缩全部图标目录...")
        zip_directory(icon_target_directory, pkg_dir / "dkapp_ico.zip", pkg_dir)
        if debug:
            ok(f"全部图标打包完成，共复制 {copied} 个图标")
    else:
        warn("未复制到任何图标，跳过打包")

def process_app_versions(app_folder: Path, template_target_directory: Path, debug: bool) -> dict[str, bool]:
    """
    压缩应用目录中的所有版本子目录。
    返回包含以下布尔标志的字典：
    - any: 是否至少压缩了一个目录
    - same: 是否压缩了与应用同名的子目录
    - other: 是否压缩了其他版本子目录
    """
    app_name = app_folder.name
    zipped_any = False
    zipped_same = False
    zipped_other = False

    for subdir in sorted(app_folder.iterdir(), key=lambda path: path.name.lower()):
        if not subdir.is_dir():
            continue

        version_name = subdir.name
        if version_name == app_name:
            zip_filename = f"{app_name}.zip"
            log_label = "已压缩同名子文件夹"
            zipped_same = True
        else:
            zip_filename = f"{app_name}-{version_name}.zip"
            log_label = "已压缩版本子文件夹"
            zipped_other = True

        zip_destination = template_target_directory / zip_filename
        zip_directory(subdir, zip_destination, subdir.parent)
        zipped_any = True
        if debug:
            ok(f"{log_label}: {subdir} -> {zip_destination}")

    return {
        "any": zipped_any,
        "same": zipped_same,
        "other": zipped_other,
    }

def process_app_info(order_file: str = 'app_order.json', output_file: str = 'apps.json', debug: int = 0):
    """
    根据 app_order.json 的顺序，合并 apps/<appname>/app.json 为单个 apps.json。
    使用混合格式化，数组内对象压缩为一行。
    """
    if not os.path.exists(order_file):
        raise FileNotFoundError(f"找不到 {order_file}")

    with open(order_file, 'r', encoding='utf-8') as f:
        order_list = json.load(f)

    if not isinstance(order_list, list):
        raise ValueError("app_order.json 必须是数组")

    apps_str = "[\n"
    missing = []

    for appname in order_list:
        app_json_path = os.path.join('apps', appname, 'app.json')
        if not os.path.exists(app_json_path):
            if debug:
                log(f"警告：未找到 {app_json_path}")
            missing.append(appname)
            continue
        with open(app_json_path, 'r', encoding='utf-8') as f:
            try:
                app_data = json.load(f)
                appdata = format_json_mixed(app_data, indent=2)
                if debug:
                    ok(f"合并 {app_json_path}")
                apps_str += appdata + ",\n"
            except json.JSONDecodeError as e:
                if debug:
                    err(f"{app_json_path} 无效 JSON: {e}")
                missing.append(appname)

    apps_str = apps_str.rstrip(",\n") + "\n]"
    with open(output_file, 'w', encoding='utf-8') as f1:
        f1.write(apps_str)

    if debug:
        log(f"生成完成: {output_file}")
        log(f"共 {len(order_list)} 个应用，缺失 {len(missing)} 个")
        if missing:
            log(f"缺失: {', '.join(missing)}")

def check_app_info(app_folder: Path, debug: int, failures: list) -> str:
    """检查 apps/<appname>/app.json 是否存在且为有效 JSON。返回 'ok' 或 'fail'。"""
    app_name = app_folder.name
    app_json = app_folder / 'app.json'
    try:
        if not app_json.exists() or not app_json.is_file():
            failures.append(f"{app_name}: 缺少应用信息 {app_json}")
            return 'fail'
        with open(app_json, 'r', encoding='utf-8') as f:
            json.load(f)
        if debug:
            ok(f"校验应用信息: {app_json} 正常")
        return 'ok'
    except Exception as e:
        failures.append(f"{app_name}: 应用信息无效 - {e}")
        return 'fail'

def process_apps(selected_apps=None, debug: int = 0):
    """
    处理 apps 目录：
    1) 复制图标到 pkg/dkapp_ico
    2) 同名子文件夹压缩为 pkg/templates/{app}.zip
    3) 其他版本子文件夹分别压缩为 pkg/templates/{app}-{version}.zip

    其他：
    - 可传入应用名列表，仅处理指定应用；不传默认处理全部
    - debug=1 详细输出；debug=0 仅输出异常
    - 记录失败项，结束统一输出（debug 时）
    """
    apps_dir = Path("apps")
    ico_target_dir = Path(".") / "pkg" / "dkapp_ico"
    template_target_directory = Path(".") / "pkg" / "templates"

    ico_target_dir.mkdir(parents=True, exist_ok=True)
    template_target_directory.mkdir(parents=True, exist_ok=True)

    all_app_dirs = [p for p in apps_dir.iterdir() if p.is_dir()]
    if selected_apps:
        name_set = set(selected_apps)
        app_dirs = [p for p in all_app_dirs if p.name in name_set]
    else:
        app_dirs = all_app_dirs

    failures = []

    # 先无条件处理所有应用图标（不受 selected_apps 影响）
    process_all_icons(apps_dir, ico_target_dir, bool(debug), failures)

    for app_folder in sorted(app_dirs, key=lambda p: p.name.lower()):
        app_name = app_folder.name
        log(f"开始处理应用: {app_name}")

        # 2) 同名子文件夹 + 3) 其他版本
        try:
            package_flags = process_app_versions(app_folder, template_target_directory, debug)
            version_status = 'ok' if package_flags["any"] else 'fail'
            if not package_flags["any"]:
                failures.append(f"{app_name}: 未找到可压缩的版本文件夹")
        except Exception as e:
            version_status = 'fail'
            failures.append(f"{app_name}: 压缩失败 - {e}")

        # 4) 应用信息校验（仅检查版本）
        is_gpu_app = ('gpu' in app_name)
        appinfo_status = None if is_gpu_app else check_app_info(app_folder, debug, failures)

        # 非 debug：仅当存在异常时输出一行汇总
        if not debug:
            has_fail = (version_status == 'fail') or (appinfo_status == 'fail' if appinfo_status is not None else False)
            if has_fail:
                version_mark = '✅版本' if version_status == 'ok' else '❌版本'
                if is_gpu_app:
                    log(f"{app_name}: {version_mark}")
                else:
                    appinfo_mark = '✅应用信息' if appinfo_status == 'ok' else '❌应用信息'
                    log(f"{app_name}: {version_mark} {appinfo_mark}")

    log("所有应用处理完成")
    if failures:
        log("以下应用处理失败：")
        for item in failures:
            log(f"- {item}")

    try:
        if debug:
            ok("开始生成 apps.json")
        process_app_info(order_file='app_order.json', output_file='pkg/apps.json', debug=debug)
        if debug:
            ok("apps.json 生成完成")
    except Exception as e:
        err(f"生成 apps.json 失败 - {e}")


# ----------------------
# CLI
# ----------------------

def main():
    parser = argparse.ArgumentParser(description="应用打包与 JSON 转换工具")
    subparsers = parser.add_subparsers(dest='cmd')

    # package (default)
    p_pkg = subparsers.add_parser('package', help='打包 apps 到 pkg')
    p_pkg.add_argument('apps', nargs='*', help='要处理的应用名（可多个）；留空表示全部应用')
    p_pkg.add_argument('--debug', type=int, choices=[0, 1], default=0, help='调试输出：1详细 0简洁，默认0')

    args = parser.parse_args()

    if args.cmd is None:
        process_apps(selected_apps=None, debug=0)
        return

    if args.cmd == 'package':
        process_apps(selected_apps=args.apps if args.apps else None, debug=args.debug)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
