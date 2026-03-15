#!/usr/bin/env python3
import os
import shutil
import string
import subprocess
import sys
import json
import requests
from dotenv import load_dotenv
real_script_path = os.path.realpath(__file__)
script_dir = os.path.dirname(real_script_path)
dotenv_path = os.path.join(script_dir, '.env')
load_dotenv(dotenv_path)

def get_contest_data_from_json(input_url):
    parts = input_url.strip().rstrip('/').split('/')
    if "atcoder.jp" in parts and 'contests' in parts:
        contest_id = parts[parts.index('contests') + 1]
        json_url = f"https://atcoder.jp/contests/{contest_id}/standings/json"

        revel_session = os.getenv("REVEL_SESSION")
        cookies = {"REVEL_SESSION": revel_session} if revel_session else {}

        try:
            response = requests.get(json_url, cookies=cookies)
            response.raise_for_status()
            data = response.json()
            task_info = data.get("TaskInfo", [])
            problem_urls = [f"https://atcoder.jp/contests/{contest_id}/tasks/{task['TaskScreenName']}" for task in task_info]
            problem_names = []
            for i in range(len(problem_urls)):
                n = i
                name = ""
                while True:
                    name = string.ascii_uppercase[n % 26] + name
                    n = n // 26 - 1
                    if n < 0:
                        break
                problem_names.append(name)
            return contest_id, f"https://atcoder.jp/contests/{contest_id}", len(task_info), problem_urls, problem_names
        except Exception as e:
            print(f"JSON取得エラー: {e}")
            return None, None, None, None, None
    elif "kenkoooo.com" in parts and "contest" in parts:
        contest_problem_json = requests.get("https://kenkoooo.com/atcoder/resources/contest-problem.json").json()
        problem_to_contest = {}
        for data in contest_problem_json:
            problem_to_contest[data["problem_id"]] = data["contest_id"]
        v_id = parts[parts.index("contest")+2]
        v_url = f'https://kenkoooo.com/atcoder/internal-api/contest/get/{v_id}'
        res = requests.get(v_url).json()
        contest_id = res["info"]["title"].replace("/","_").replace(" ","_")
        problems = [p["id"] for p in res["problems"]]
        problem_urls = []
        for problem in problems:
            cid = problem_to_contest[problem]
            problem_urls.append(f"https://atcoder.jp/contests/{cid}/tasks/{problem}")
        problem_names = []
        for i in range(len(problem_urls)):
            n = i
            name = ""
            while True:
                name = string.ascii_uppercase[n % 26] + name
                n = n // 26 - 1
                if n < 0:
                    break
            problem_names.append(name)
        return contest_id, input_url, len(problems), problem_urls, problem_names
    elif "yukicoder.me" in parts:
        #print("yukicoder")
        cid = parts[parts.index("yukicoder.me") + 2]
        contest_problem_json = requests.get(f"https://yukicoder.me/api/v1/contest/id/{cid}").json()
        #print(contest_problem_json)
        problems = contest_problem_json["Problems"]
        problem_urls = []
        for problem in problems:
            #print(problem)
            no = problem["No"]
            problem_urls.append(f"https://yukicoder.me/problems/no/{no}")
        problem_names = []
        for i in range(len(problem_urls)):
            n = i
            name = ""
            while True:
                name = string.ascii_uppercase[n % 26] + name
                n = n // 26 - 1
                if n < 0:
                    break
            problem_names.append(name)
        return contest_problem_json["Name"].replace(" ","_"),input_url,len(problems),problem_urls,problem_names
    else:
        print("コンテストの取得に失敗しました。")
        return None, None, None, None, None

def setup_contest(contest_id, contest_url, num_problems, problem_urls, problem_names):
    working_dir = os.path.dirname(os.path.realpath(__file__))
    script_dir = os.path.dirname(os.path.realpath(__file__))
    
    base_dir = os.path.join(working_dir, "contests", contest_id)
    template_dir = os.path.join(script_dir, "template")
    dot_vscode_src = os.path.join(script_dir, ".vscode")
    cplib_path = os.getenv("CPLIB_PATH")
    nimacl_path = os.getenv("NIM_ACL_PATH")
    if not os.path.exists(template_dir):
        print(f"Error: {template_dir} が見つかりません。")
        return

    # 1. 各問題フォルダ作成とテンプレート処理
    for i in range(num_problems):
        name = problem_names[i]
        target_path = os.path.join(base_dir, name)
        new_main_filename = f"{name}.nim"
        
        if os.path.exists(target_path):
            print(f"Skipped: '{name}' フォルダは既に存在するためスキップします。")
            continue
            
        os.makedirs(target_path, exist_ok=True)
        shutil.copytree(template_dir, target_path, dirs_exist_ok=True)
        
        # Main.nim を {name}.nim にリネーム
        old_file = os.path.join(target_path, "Main.nim")
        new_file = os.path.join(target_path, new_main_filename)
        if os.path.exists(old_file):
            os.rename(old_file, new_file)

        # フォルダ内の全ファイルの __mainname__ を置換
        for root, dirs, files in os.walk(target_path):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    # 置換処理 (例: __mainname__ -> A.nim)
                    if "__mainname__" in content:
                        new_content = content.replace("__mainname__", new_main_filename)
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(new_content)
                except Exception as e:
                    # バイナリファイル等で読み込めない場合はスキップ
                    pass

    # 2. .vscode のコピー
    if os.path.exists(dot_vscode_src):
        target_vscode = os.path.join(base_dir, ".vscode")
        shutil.copytree(dot_vscode_src, target_vscode, dirs_exist_ok=True)
        # .vscodeをコピーしたのちに、置き換え処理を行う。
        for root, dirs, files in os.walk(target_vscode):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    # 置換処理 (例: __mainname__ -> A.nim)
                    if "__cplibpath__" in content or "__nimacl__" in content:
                        new_content = content.replace("__cplibpath__", cplib_path).replace("__nimacl__",nimacl_path)
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(new_content)
                except Exception as e:
                    # バイナリファイル等で読み込めない場合はスキップ
                    pass

    # 3. マルチワークスペースファイル作成
    workspace_data = {
        "folders": [
            {"name": f"Contest: {contest_id}", "path": "."},
            {"name": "Library (src)", "path": cplib_path + "/src"}
        ],
        "settings": {
            "nim.buildCommand": "cpp"
        }
    }
    workspace_path = os.path.join(base_dir, f"{contest_id}.code-workspace")
    with open(workspace_path, "w", encoding="utf-8") as f:
        json.dump(workspace_data, f, indent=4)

    # 4. config / dlall / suball
    with open(os.path.join(base_dir, "config"), "w") as f:
        f.write(f"CONTEST_ID: {contest_id}\nURL: {contest_url}\n")

    dlall_path = os.path.join(base_dir, "dlall")
    with open(dlall_path, "w") as f:
        f.write("#!/bin/bash\n\n")
        for p_name in problem_names:
            f.write(f"code ./{p_name}/{p_name}.nim\n")
        f.write(f"code ./{problem_names[0]}/{problem_names[0]}.nim\n")
        for i, p_name in enumerate(problem_names):
            f.write(f"cd {p_name} && oj d {problem_urls[i]}; cd ..\n")
    os.chmod(dlall_path, 0o755)
    
    dlopen_path = os.path.join(base_dir, "dlopen")
    with open(dlopen_path, "w") as f:
        f.write("#!/bin/bash\n\n")
        f.write(f'cmd.exe /c start "" "{problem_urls[0]}" >/dev/null 2>&1 \n')
        for i, p_name in enumerate(problem_names):
            f.write(f"code ./{p_name}/{p_name}.nim\n")
        f.write(f"code ./{problem_names[0]}/{problem_names[0]}.nim\n")
        for i, p_name in enumerate(problem_names):
            f.write(f"cd {p_name} && oj d {problem_urls[i]}; cd ..\n")
    os.chmod(dlopen_path, 0o755)
    
    suball_path = os.path.join(base_dir, "suball")
    with open(suball_path, "w") as f:
        f.write("#!/bin/bash\n\n")
        for p_name in problem_names:
            f.write(f"cd {p_name} && ./sub && cd ..\n")
    os.chmod(suball_path, 0o755)
# === ここから追加: next_prob.sh の作成 (動的取得版) ===
    next_prob_path = os.path.join(base_dir, "next_prob.sh")
    with open(next_prob_path, "w", encoding="utf-8") as f:
        f.write("#!/bin/bash\n\n")
        
        # URLとディレクトリ名の配列をシェルスクリプトに埋め込む
        urls_str = " ".join([f'"{u}"' for u in problem_urls])
        dirs_str = " ".join([f'"{d}"' for d in problem_names])
        f.write(f'URLS=({urls_str})\n')
        f.write(f'DIRS=({dirs_str})\n\n')
        
        # VS Codeから渡された現在開いているファイル名（拡張子なし）を取得
        f.write('CURRENT_PROB="$1"\n')
        f.write('NEXT_IDX=0\n\n')
        
        # 現在の問題が配列の何番目かを探す
        f.write('for i in "${!DIRS[@]}"; do\n')
        f.write('    if [[ "${DIRS[$i]}" == "$CURRENT_PROB" ]]; then\n')
        f.write('        NEXT_IDX=$((i + 1))\n')
        f.write('        break\n')
        f.write('    fi\n')
        f.write('done\n\n')
        
        # 最後の問題だったら最初に戻る
        f.write('if [ "$NEXT_IDX" -ge "${#DIRS[@]}" ]; then\n')
        f.write('    NEXT_IDX=0\n')
        f.write('fi\n\n')
        
        f.write('echo "Opening problem: ${DIRS[$NEXT_IDX]}"\n')
        f.write('cmd.exe /c start "" "${URLS[$NEXT_IDX]}" >/dev/null 2>&1 \n')
        f.write('code -g "' + base_dir + '/${DIRS[$NEXT_IDX]}/${DIRS[$NEXT_IDX]}.nim:99999"\n')
    os.chmod(next_prob_path, 0o755)
    # === 追加ここまで ===
    # === 追加ここまで ===

    # 5. VS Codeでワークスペースを開く
    try:
        subprocess.run(["code", workspace_path], check=False)
        print(f"Opened workspace: {workspace_path}")
    except FileNotFoundError:
        print("Warning: 'code' command not found.")

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else input("AtCoder URL: ")
    res = get_contest_data_from_json(url)
    if res and res[0]:
        setup_contest(*res)