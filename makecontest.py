#!/usr/bin/env python3
import os
import shutil
import string
import subprocess
import sys
import json
import requests
from dotenv import load_dotenv

# .envからREVEL_SESSIONを取得
load_dotenv()

def get_contest_data_from_json(input_url):
    parts = input_url.strip().rstrip('/').split('/')
    if 'contests' not in parts:
        print("エラー: 有効なAtCoderのコンテストURLではありません。")
        return None, None
    
    contest_id = parts[parts.index('contests') + 1]
    json_url = f"https://atcoder.jp/contests/{contest_id}/standings/json"

    revel_session = os.getenv("REVEL_SESSION")
    cookies = {"REVEL_SESSION": revel_session} if revel_session else {}

    try:
        response = requests.get(json_url, cookies=cookies)
        response.raise_for_status()
        data = response.json()
        task_info = data.get("TaskInfo", [])
        return contest_id, len(task_info)
    except Exception as e:
        print(f"JSON取得エラー: {e}")
        return None, None

def setup_contest(contest_id, num_problems):
    # パス設定
    working_dir = os.path.abspath(".")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    base_dir = os.path.join(working_dir, "contests", contest_id)
    template_dir = os.path.join(script_dir, "template")
    dot_vscode_src = os.path.join(script_dir, ".vscode")
    cplib_path = "/home/kemuniku/atcoder/cplib/src" # ライブラリのパス
    
    contest_url = f"https://atcoder.jp/contests/{contest_id}"

    if not os.path.exists(template_dir):
        print(f"Error: {template_dir} が見つかりません。")
        return

    # 1. 各問題フォルダ作成とテンプレートコピー
    problem_names = []
    for i in range(num_problems):
        name = ""
        n = i
        while True:
            name = string.ascii_uppercase[n % 26] + name
            n = n // 26 - 1
            if n < 0:
                break
        problem_names.append(name)
        target_path = os.path.join(base_dir, name)
        os.makedirs(target_path, exist_ok=True)
        shutil.copytree(template_dir, target_path, dirs_exist_ok=True)

    # 2. .vscode のコピー
    if os.path.exists(dot_vscode_src):
        target_vscode = os.path.join(base_dir, ".vscode")
        shutil.copytree(dot_vscode_src, target_vscode, dirs_exist_ok=True)

    # 3. マルチルート・ワークスペースファイルの作成
    # このファイルを開くと、コンテストフォルダとcplibが両方サイドバーに出ます
    workspace_data = {
        "folders": [
            {
                "name": f"Contest: {contest_id}",
                "path": "."
            },
            {
                "name": "Library (src)",
                "path": cplib_path
            }
        ],
        "settings": {
            # 起動時にターミナルを自動で開くための設定
            "terminal.integrated.showOnStartup": "always",
            # ターミナルに最初からフォーカスを当てる
            "terminal.integrated.focusAfterLaunch": True,
            # ワークスペースを開いたときにパネル（ターミナル等）の状態を復元する
            "workbench.panel.defaultLocation": "bottom",
            "workbench.panel.opensMaximized": "never"
        }
    }
    workspace_path = os.path.join(base_dir, f"{contest_id}.code-workspace")
    with open(workspace_path, "w", encoding="utf-8") as f:
        json.dump(workspace_data, f, indent=4)

    # 4. configファイルとdlallスクリプト
    with open(os.path.join(base_dir, "config"), "w") as f:
        f.write(f"CONTEST_ID: {contest_id}\nURL: {contest_url}\n")

    dlall_path = os.path.join(base_dir, "dlall")
    with open(dlall_path, "w") as f:
        f.write("#!/bin/bash\n\n")
        for p_name in problem_names:
            p_id = f"{contest_id}_{p_name.lower()}"
            f.write(f"cd {p_name} && oj d {contest_url}/tasks/{p_id} && cd ..\n")
    os.chmod(dlall_path, 0o755)

    # 5. VS Codeでワークスペースを開く
    try:
        # ディレクトリではなく .code-workspace ファイルを渡す
        subprocess.run(["code", workspace_path], check=False)
        print(f"Opened workspace: {workspace_path}")
    except FileNotFoundError:
        print("Warning: 'code' command not found.")

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else input("AtCoder URL: ")
    c_id, n_probs = get_contest_data_from_json(url)
    if c_id and n_probs:
        setup_contest(c_id, n_probs)