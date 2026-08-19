"""
Safe GitHub Repository Push Helper.
"""
import subprocess
import sys


def run_cmd(cmd: str):
    res = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    if res.stdout:
        print(res.stdout.strip())
    if res.stderr and "warning:" not in res.stderr.lower():
        print(res.stderr.strip())
    return res.returncode


def main():
    print("=" * 60)
    print("  LOSSLESS STUDIO - Отправка на GitHub для сборки APK")
    print("=" * 60)
    print()

    repo_url = input("Вставьте ссылку на ваш GitHub репозиторий: ").strip()
    if not repo_url:
        print("\n[Ошибка] Ссылка не была введена.")
        input("\nНажмите Enter для выхода...")
        return

    print("\n[1/3] Настройка удаленного репозитория...")
    run_cmd("git remote remove origin")
    code = run_cmd(f'git remote add origin "{repo_url}"')
    run_cmd("git branch -M main")

    print("[2/3] Подготовка и фиксация файлов...")
    run_cmd("git add .")
    run_cmd('git commit -m "update files for android build"')

    print(f"[3/3] Отправка файлов в {repo_url}...")
    code = run_cmd("git push -u origin main --force")

    print("\n" + "=" * 60)
    if code == 0:
        print("✓ УСПЕХ: Файлы успешно отправлены на GitHub!")
        print("Сборка APK на сервере GitHub началась автоматически.")
        print("Откройте вкладку 'Actions' в вашем репозитории на GitHub,")
        print("чтобы скачать готовый файл LosslessStudio-Android-APK (.apk).")
    else:
        print("Если появилась ошибка аутентификации, убедитесь, что вы")
        print("вошли в аккаунт GitHub или используете Personal Access Token.")
    print("=" * 60)
    input("\nНажмите Enter для завершения...")


if __name__ == "__main__":
    main()
