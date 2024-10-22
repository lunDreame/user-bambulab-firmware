import os
import requests
import json
from typing import Optional, List, Dict, Tuple
from github import Github, InputGitAuthor, GithubException

class BambuLabOTA:
    def __init__(self):
        self.account = os.getenv("BAMBU_ACCOUNT")
        self.password = os.getenv("BAMBU_PASSWORD")
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.repo_name = "lunDreame/user-bambulab-firmware"
        self.author_name = "lunDreame34"
        self.author_email = "lundreame34@gmail.com"
        self.login_url = "https://bambulab.com/api/sign-in/form"
        self.api_url = "https://api.bambulab.com"
        self.device_id = None
        self.access_token = None
        self.github = Github(self.github_token)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

        self.login()

    def login(self):
        try:
            response = requests.post(
                self.login_url, 
                headers=self.headers,
                data={"account": self.account, "password": self.password}
            )
            response.raise_for_status()
            self.access_token = response.cookies.get("token")
            if response.status_code == 200 and not response.json().get("tfaKey"):
                print("Login Successful.")
                self.get_user_devices()
            else:
                print("Login Failed.")
        except requests.RequestException as e:
            print(f"An error occurred during login: {e}")

    def get_user_devices(self):
        headers = {
            **self.headers,
            "authorization": f"Bearer {self.access_token}"
        }
        try:
            response = requests.get(
                f"{self.api_url}/v1/iot-service/api/user/bind", 
                headers=headers
            )
            response.raise_for_status()
            devices = response.json().get("devices", [])
            self.select_device(devices)
        except requests.RequestException as e:
            print(f"An error occurred while getting bound devices: {e}")

    def select_device(self, devices: List[Dict]):
        if not devices:
            print("No devices found.")
            return
        try:
            selected_index = 0
            selected_device = devices[selected_index]
            self.device_id = selected_device["dev_id"]
            print(f"\n선택된 디바이스 정보:")
            print(f"Device ID: {selected_device['dev_id']}")
            print(f"Device Name: {selected_device.get('name', 'N/A')}")
            print(f"Device Model: {selected_device.get('dev_model', 'N/A')}\n")
            self.get_device_version()
        except (IndexError, ValueError) as e:
            print(f"Invalid index selected: {e}")

    def get_device_version(self):
        headers = {
            **self.headers,
            "authorization": f"Bearer {self.access_token}"
        }
        try:
            response = requests.get(
                f"{self.api_url}/v1/iot-service/api/user/device/version?dev_id={self.device_id}", 
                headers=headers
            )
            response.raise_for_status()
            device_version_info = response.json()
            
            print("\n펌웨어 정보:")
            print("=" * 50)
            devices = device_version_info.get("devices", [])
            if devices:
                device = devices[0]
                print(f"Device Model: {device.get('dev_model', 'N/A')}")
                print(f"Device ID: {device.get('dev_id', 'N/A')}")
                
                for firmware in device.get("firmware", []):
                    print("\nFirmware Details:")
                    print(f"Version: {firmware.get('version', 'N/A')}")
                    print(f"Module: {firmware.get('module', 'N/A')}")
                    print(f"Description: {firmware.get('description', 'N/A')}")
                    print(f"URL: {firmware.get('url', 'N/A')}")
                    print(f"Force Update: {firmware.get('force_update', False)}")
                    print(f"Status: {firmware.get('status', 'N/A')}")
            print("=" * 50)
            print()
            
            printer_name, firmware_optional = self.construct_firmware_optional(device_version_info)
            
            for version in ("C11", "C12"):
                firmware_optional_copy = firmware_optional.copy()
                firmware_optional_copy["upgrade"]["firmware_optional"]["firmware"]["url"] = \
                firmware_optional_copy["upgrade"]["firmware_optional"]["firmware"]["url"].replace("C11", version)
                
                print(f"\n{version} 펌웨어 옵션:")
                print(json.dumps(firmware_optional_copy, indent=4, ensure_ascii=False))
                print("=" * 50)
                
                self.compare_and_create_pull_request(printer_name, firmware_optional_copy)
        except requests.RequestException as e:
            print(f"An error occurred while getting the device version: {e}")

    def construct_firmware_optional(self, device_version_info: Dict) -> Tuple[str, Dict]:
        device_id_map = {
            "00M": "X1C",
            "00W": "X1",
            "01S": "P1P",
            "01P": "P1S",
            "030": "A1_MINI",
            "039": "A1"
        }
        printer_name = next((name for prefix, name in device_id_map.items() if self.device_id.startswith(prefix)), "Unknown")
        print(f"\n프린터 모델: {printer_name}")
        
        firmware_info = device_version_info["devices"][0]["firmware"][0]
        firmware_optional = {
            "user_id": "0",
            "upgrade": {
                "sequence_id": "0",
                "command": "upgrade_history",
                "src_id": 2,
                "firmware_optional": {
                    "firmware": {
                        "version": firmware_info["version"],
                        "url": firmware_info["url"],
                        "force_update": False,
                        "description": firmware_info["description"],
                        "status": "release"
                    },
                    "ams": [] if self.device_id.startswith(("030", "039")) else [{
                        "dev_model_name": "BL-A001",
                        "address": 0,
                        "device_id": "",
                        "firmware": [{
                            "version": "00.00.06.40",
                            "force_update": False,
                            "url": "https://public-cdn.bambulab.com/upgrade/device/BL-A001/00.00.06.40/product/ams-ota_v00.00.06.40-20230906131441.json.sig",
                            "description": "",
                            "status": "testing"
                        }],
                        "firmware_current": None
                    }]
                }
            }
        }
        return printer_name, firmware_optional

    def compare_and_create_pull_request(self, printer_name: str, firmware_optional: Dict):
        new_content = json.dumps(firmware_optional, indent=4)
        new_ota_version = json.loads(new_content)["upgrade"]["firmware_optional"]["firmware"]["version"]
        file_path = f"assets/{printer_name}_AMS.json"
        repo = self.github.get_repo(self.repo_name)
        branch_name = "schedule-update"

        try:
            contents = repo.get_contents(file_path, ref="main")
            old_content = contents.decoded_content.decode("utf-8")
            old_ota_version = json.loads(old_content)["upgrade"]["firmware_optional"]["firmware"]["version"]

            print(f"\n버전 비교:")
            print(f"현재 버전: {old_ota_version}")
            print(f"새 버전: {new_ota_version}")

            if new_ota_version == old_ota_version:
                print("No changes detected in the OTA version.")
                return
            else:
                print("Changes detected, updating file and creating a pull request.")
                self.update_file(repo, file_path, new_content, contents.sha, branch_name)
        except GithubException as e:
            if e.status == 404:
                print("File does not exist, creating a new one.")
                try:
                    self.create_branch(repo, branch_name)
                    self.create_file(repo, file_path, new_content, branch_name)
                except GithubException as e:
                    print(f"Error creating branch or file: {e}")
                    return

        self.create_pull_request(repo, branch_name, printer_name)

    def update_file(self, repo, file_path, content, sha, branch_name):
        try:
            contents = repo.get_contents(file_path, ref="main")
            sha = contents.sha
            repo.update_file(
                file_path,
                f"Update {file_path}",
                content,
                sha,
                branch=branch_name,
                author=InputGitAuthor(self.author_name, self.author_email)
            )
            print(f"File {file_path} updated successfully.")
        except GithubException as e:
            print(f"Error updating file: {e}")

    def create_file(self, repo, file_path, content, branch_name):
        try:
            main_ref = repo.get_git_ref("heads/main")
            repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=main_ref.object.sha)
            
            repo.create_file(
                file_path,
                f"Create {file_path}",
                content,
                branch=branch_name,
                author=InputGitAuthor(self.author_name, self.author_email)
            )
            print(f"File {file_path} created successfully.")
        except GithubException as e:
            print(f"Error creating file or branch: {e}")

    def create_pull_request(self, repo, branch_name, printer_name):
        try:
            repo.create_pull(
                title=f"Update {printer_name}_AMS JSON file",
                body=f"The {printer_name}_AMS JSON file has been updated.",
                head=branch_name,
                base="main"
            )
            print("Pull request created successfully.")
        except GithubException as e:
            print(f"Error creating pull request: {e}")

if __name__ == '__main__':
    BambuLabOTA()
