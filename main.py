# -*- coding: utf-8 -*-
"""
Lite Launcher v20 – добавлен ASCII-арт в меню
Полностью автономный, использует Oracle JDK для всех версий
"""

import os
import sys
import json
import subprocess
import shutil
import zipfile
import tempfile
from pathlib import Path
import requests
import minecraft_launcher_lib as mll

# ------------------- Конфигурация -------------------
CONFIG_FILE = "lite_launcher_config.json"
DEFAULT_CONFIG = {
    "ram_mb": 4096,
    "nickname": "Player",
    "minecraft_dir": str(Path.home() / "AppData" / "Roaming" / ".minecraft_lite"),
    "selected_version": "1.20.4"
}

BASE_JAVA_DIR = Path("java_runtime")

# ------------------- Работа с конфигом -------------------
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4, ensure_ascii=False)

# ------------------- Определение требуемой версии Java -------------------
def get_required_java_version(version_id):
    try:
        version_info = mll.utils.get_version_info(version_id)
        if "javaVersion" in version_info:
            if "majorVersion" in version_info["javaVersion"]:
                return str(version_info["javaVersion"]["majorVersion"])
    except Exception:
        pass

    vid = version_id.lower()
    if vid.startswith("inf-") or vid.startswith("a-") or vid.startswith("b-") or vid.startswith("c-"):
        return "8"

    if vid.startswith("1."):
        try:
            parts = vid.split(".")
            if len(parts) >= 2:
                minor = int(parts[1])
                if minor >= 21:
                    return "21"
                elif minor >= 17:
                    return "17"
                else:
                    return "8"
        except ValueError:
            pass

    if vid.startswith("26.") or vid.startswith("27.") or vid.startswith("28."):
        return "25"

    return "21"

# ------------------- Получение ссылок на Oracle JDK -------------------
def get_java_download_url(java_version):
    oracle_urls = {
        "25": "https://download.oracle.com/java/25/archive/jdk-25.0.2_windows-x64_bin.zip",
        "21": "https://download.oracle.com/java/21/archive/jdk-21.0.4_windows-x64_bin.zip",
        "17": "https://download.oracle.com/java/17/archive/jdk-17.0.10_windows-x64_bin.zip",
        "8":  "https://download.oracle.com/java/8/archive/jdk-8u402-windows-x64.zip"
    }
    if java_version in oracle_urls:
        return oracle_urls[java_version]

    api_url = f"https://api.adoptium.net/v3/assets/version/{java_version}/hotspot?architecture=x64&image_type=jre&os=windows&project=jdk"
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
    try:
        resp = session.get(api_url, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            if data and len(data) > 0:
                for asset in data:
                    if asset.get("binary") and asset["binary"].get("package"):
                        link = asset["binary"]["package"].get("link")
                        if link:
                            return link
    except Exception:
        pass

    fallbacks = {
        "11": "https://github.com/adoptium/temurin11-binaries/releases/download/jdk-11.0.22%2B7/OpenJDK11U-jre_x64_windows_hotspot_11.0.22_7.zip"
    }
    return fallbacks.get(java_version, None)

# ------------------- Управление Java -------------------
def ensure_java(required_version):
    java_dir = BASE_JAVA_DIR / required_version
    java_exe = java_dir / "bin" / "java.exe"

    if java_exe.exists():
        try:
            out = subprocess.check_output([str(java_exe), "-version"], stderr=subprocess.STDOUT, text=True)
            if required_version in out:
                return str(java_exe)
        except:
            pass

    try:
        out = subprocess.check_output(["java", "-version"], stderr=subprocess.STDOUT, text=True)
        if required_version in out:
            print(f"Системная Java {required_version} найдена. Используем её.")
            return "java"
    except:
        pass

    print(f"Java {required_version} не найдена. Загрузка и установка (это займёт несколько минут)...")

    download_url = get_java_download_url(required_version)
    if not download_url:
        print(f"Не удалось получить ссылку для Java {required_version}. Установите вручную.")
        sys.exit(1)

    java_dir.mkdir(parents=True, exist_ok=True)
    zip_path = java_dir / "jre.zip"

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.oracle.com/",
        "Accept": "application/zip"
    })
    try:
        response = session.get(download_url, stream=True, timeout=120)
        if response.status_code != 200:
            print(f"Ошибка загрузки: код {response.status_code}")
            if required_version in ("21", "17", "8"):
                fallback_url = {
                    "21": "https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.4%2B7/OpenJDK21U-jre_x64_windows_hotspot_21.0.4_7.zip",
                    "17": "https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.10%2B7/OpenJDK17U-jre_x64_windows_hotspot_17.0.10_7.zip",
                    "8":  "https://github.com/adoptium/temurin8-binaries/releases/download/jdk8u402-b06/OpenJDK8U-jre_x64_windows_hotspot_8u402b06.zip"
                }
                print(f"Пробуем запасной URL (Adoptium) для Java {required_version}...")
                response = session.get(fallback_url[required_version], stream=True, timeout=120)
                if response.status_code != 200:
                    print("Запасной URL не работает. Установите Java вручную.")
                    sys.exit(1)
            else:
                print("Запасной URL не доступен. Установите Java вручную.")
                sys.exit(1)
    except Exception as e:
        print(f"Ошибка при загрузке: {e}")
        sys.exit(1)

    total = int(response.headers.get('content-length', 0))
    with open(zip_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

    with open(zip_path, 'rb') as f:
        if f.read(4) != b'PK\x03\x04':
            print("Скачанный файл не является zip-архивом. Удаляем.")
            os.remove(zip_path)
            sys.exit(1)

    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(tmpdir)
        extracted = list(Path(tmpdir).iterdir())
        if len(extracted) != 1:
            print("Ошибка: в архиве не одна папка.")
            sys.exit(1)
        src = extracted[0]
        if java_dir.exists():
            shutil.rmtree(java_dir)
        shutil.copytree(src, java_dir)

    try:
        os.remove(zip_path)
    except FileNotFoundError:
        pass

    if java_exe.exists():
        print(f"Java {required_version} успешно установлена.")
        return str(java_exe)
    else:
        print(f"Ошибка установки Java {required_version}: не найден java.exe.")
        sys.exit(1)

# ------------------- Проверка установленной версии Minecraft -------------------
def is_version_installed(version_id, minecraft_dir):
    version_path = Path(minecraft_dir) / "versions" / version_id
    return version_path.exists() and (version_path / f"{version_id}.jar").exists()

# ------------------- Установка версии Minecraft -------------------
def install_version(version_id, minecraft_dir):
    print(f"Установка версии {version_id}...")
    callback = {
        "setMax": lambda max_val: print(f"Всего файлов: {max_val}"),
        "setProgress": lambda current, total=None: print(f"\rПрогресс: {int(current/(total if total else 1)*100)}% ({current}/{total if total else 1})", end="") if total else None,
        "setStatus": lambda status: print(f"\nСтатус: {status}")
    }
    try:
        mll.install.install_minecraft_version(version_id, minecraft_dir, callback=callback)
        print("\nУстановка завершена.")
    except Exception as e:
        print(f"\nОшибка установки с callback: {e}")
        try:
            mll.install.install_minecraft_version(version_id, minecraft_dir)
            print("Установка завершена (без callback).")
        except Exception as e2:
            print(f"Критическая ошибка установки: {e2}")
            sys.exit(1)

# ------------------- Запуск Minecraft -------------------
def launch_minecraft(config):
    version = config["selected_version"]
    required_java = get_required_java_version(version)
    print(f"Для версии {version} требуется Java {required_java}")

    java_path = ensure_java(required_java)
    minecraft_dir = config["minecraft_dir"]
    nickname = config["nickname"]
    ram = config["ram_mb"]

    if not is_version_installed(version, minecraft_dir):
        print(f"Версия {version} не установлена. Установка...")
        install_version(version, minecraft_dir)

    options = {
        "username": nickname,
        "uuid": "00000000-0000-0000-0000-000000000000",
        "token": "",
        "jvmArguments": [f"-Xmx{ram}M", f"-Xms{ram//2}M"],
        "executablePath": java_path,
        "gameDirectory": minecraft_dir
    }
    command = mll.command.get_minecraft_command(version, minecraft_dir, options)
    filtered = []
    for arg in command:
        if arg.startswith("--sun-misc-unsafe") or arg.startswith("--enable-native-access"):
            continue
        if "--sun-misc-unsafe-memory-access=allow" in arg:
            continue
        filtered.append(arg)
    command = filtered
    print(f"Запуск: {' '.join(command)}")
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Ошибка запуска (код {e.returncode}). Проверьте версию Java и файлы.")
        input("Нажмите Enter...")

# ------------------- Получение списка версий (прямой запрос к Mojang) -------------------
def get_version_list():
    url = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"
    try:
        response = requests.get(url, timeout=15)
        if response.status_code != 200:
            raise RuntimeError(f"HTTP {response.status_code}")
        manifest = response.json()
        versions = manifest.get("versions", [])
        releases = [v for v in versions if v.get("type") == "release"]
        snapshots = [v for v in versions if v.get("type") == "snapshot"]
        old = [v for v in versions if v.get("type") in ("old_alpha", "old_beta")]
        return releases, snapshots, old
    except Exception as e:
        try:
            manifest = mll.utils.get_manifest()
            versions = manifest["versions"]
            releases = [v for v in versions if v["type"] == "release"]
            snapshots = [v for v in versions if v["type"] == "snapshot"]
            old = [v for v in versions if v["type"] in ("old_alpha", "old_beta")]
            return releases, snapshots, old
        except:
            raise RuntimeError(f"Не удалось загрузить список версий: {e}")

# ------------------- Меню с ASCII-артом -------------------
def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def print_header():
    print("""
 _     _ _       _                            _                     
| |   (_) |     | |                          | |                _   
| |    _| |_ ___| |     __ _ _   _ _ __   ___| |__   ___ _ __ _| |_ 
| |   | | __/ _ \ |    / _` | | | | '_ \ / __| '_ \ / _ \ '__|_   _|
| |___| | ||  __/ |___| (_| | |_| | | | | (__| | | |  __/ |    |_|  
\_____/_|\__\___\_____/\__,_|\__,_|_| |_|\___|_| |_|\___|_|
    """)
    print("="*40)
    print("          Lite Launcher +")
    print("="*40)

def main_menu(config):
    while True:
        clear_screen()
        print_header()
        print("1: Запустить Minecraft")
        print("2: Настройки")
        print("3: Выбрать версию")
        print("0: Выход")
        choice = input("> ").strip()
        if choice == "1":
            launch_minecraft(config)
            input("Нажмите Enter для продолжения...")
        elif choice == "2":
            settings_menu(config)
        elif choice == "3":
            version_menu(config)
        elif choice == "0":
            print("Выход.")
            break
        else:
            print("Неверный выбор.")

def settings_menu(config):
    while True:
        clear_screen()
        print_header()
        print("Настройки:")
        print(f"1: RAM (текущий: {config['ram_mb']} МБ)")
        print(f"2: Nickname (текущий: {config['nickname']})")
        print(f"3: Папка Minecraft (текущий: {config['minecraft_dir']})")
        print("0: Выход")
        choice = input("> ").strip()
        if choice == "1":
            try:
                val = input(f"Введите RAM в МБ (целое число, мин 512): ")
                if val.strip():
                    ram = int(val)
                    if ram >= 512:
                        config["ram_mb"] = ram
                        save_config(config)
                        print("Обновлено.")
                    else:
                        print("Минимум 512 МБ.")
                else:
                    print("Отмена.")
            except ValueError:
                print("Ошибка ввода.")
            input("Нажмите Enter...")
        elif choice == "2":
            nick = input(f"Введите никнейм (текущий {config['nickname']}): ").strip()
            if nick:
                config["nickname"] = nick
                save_config(config)
                print("Обновлено.")
            else:
                print("Отмена.")
            input("Нажмите Enter...")
        elif choice == "3":
            path = input(f"Введите путь к папке Minecraft (текущий {config['minecraft_dir']}): ").strip()
            if path:
                Path(path).mkdir(parents=True, exist_ok=True)
                config["minecraft_dir"] = path
                save_config(config)
                print("Обновлено.")
            else:
                print("Отмена.")
            input("Нажмите Enter...")
        elif choice == "0":
            break
        else:
            print("Неверный выбор.")

def version_menu(config):
    print("Загрузка списка версий...")
    try:
        releases, snapshots, old = get_version_list()
    except Exception as e:
        print(f"Ошибка загрузки: {e}. Проверьте интернет.")
        input("Нажмите Enter...")
        return

    while True:
        clear_screen()
        print_header()
        print("Выбор версии:")
        print(f"Текущая: {config['selected_version']}")
        print("1: Релизы")
        print("2: Снапшоты")
        print("3: Старые (alpha/beta)")
        print("0: Выход")
        choice = input("> ").strip()
        if choice == "1":
            show_version_list(releases, config, "Релизы")
        elif choice == "2":
            show_version_list(snapshots, config, "Снапшоты")
        elif choice == "3":
            show_version_list(old, config, "Старые")
        elif choice == "0":
            break
        else:
            print("Неверный выбор.")

def show_version_list(versions, config, title):
    versions_sorted = sorted(versions, key=lambda v: v["releaseTime"], reverse=True)
    total = len(versions_sorted)
    if total == 0:
        print("Нет версий в этой категории.")
        input("Нажмите Enter...")
        return
    page = 0
    page_size = 15
    while True:
        clear_screen()
        print_header()
        print(f"{title} (стр. {page+1}/{(total-1)//page_size+1})")
        start = page * page_size
        end = min(start + page_size, total)
        for i, v in enumerate(versions_sorted[start:end], start=start+1):
            print(f"{i}: {v['id']}")
        print("0: Назад")
        print("Введите номер версии для выбора, или 'n'/'p' для страниц, или 0 для выхода.")
        choice = input("> ").strip()
        if choice == "0":
            break
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < total:
                selected = versions_sorted[idx]["id"]
                config["selected_version"] = selected
                save_config(config)
                print(f"Выбрана версия {selected}")
                input("Нажмите Enter...")
                break
            else:
                print("Номер вне диапазона.")
                input("Нажмите Enter...")
        else:
            if choice.lower() == "n" and end < total:
                page += 1
            elif choice.lower() == "p" and page > 0:
                page -= 1
            else:
                print("Неверный ввод.")
                input("Нажмите Enter...")

# ------------------- Точка входа -------------------
if __name__ == "__main__":
    config = load_config()
    Path(config["minecraft_dir"]).mkdir(parents=True, exist_ok=True)
    main_menu(config)