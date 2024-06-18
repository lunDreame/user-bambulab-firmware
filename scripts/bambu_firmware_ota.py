import os
import requests
import json
from typing import Optional, List, Dict
from github import Github, InputGitAuthor, GithubException

class BambuLabOTA:
    def __init__(self):
        self.account = os.getenv("BAMBU_ACCOUNT")
        self.password = os.getenv("BAMBU_PASSWORD")
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.repo_name = "lunDreame/user-bambulab-firmware"
        self.author_name = "lunDreame"
        self.author_email = "lundreame34@gmail.com"
        self.login_url = "https://bambulab.com/api/sign-in/form"
        self.api_url = "https://api.bambulab.com"
        self.device_id = None
        self.access_token = None
        self.github = Github(self.github_token)

        if not self.account or not self.password or not self.github_token:
            self.prompt_user_account()
        else:
            self.login()

    def prompt_user_account(self):
        self.account = input("Please enter your Bambu Lab cloud account: ")
        self.password = input("Please enter the password for the Bambu Lab Cloud: ")
        self.github_token = input("Please enter your GitHub token: ")
        self.login()

    def login(self):
        try:
            response = requests.post(self.login_url, data={"account": self.account, "password": self.password})
            response.raise_for_status()
            self.access_token = response.cookies.get("token")
            if response.status_code == 200 and not response.json().get("tfaKey"):
                print("BambuLab Cloud Login Successful")
                self.get_user_devices()
            else:
                print(f"BambuLab Cloud Login Failed: {response.json()}")
        except requests.RequestException as e:
            print(f"An error occurred during login: {e}")

    def get_user_devices(self):
        try:
            response = requests.get(f"{self.api_url}/v1/iot-service/api/user/bind", headers={"authorization": f"Bearer {self.access_token}"})
            response.raise_for_status()
            devices = response.json().get("devices", [])
            self.select_device(devices)
        except requests.RequestException as e:
            print(f"An error occurred while getting bound devices: {e}")

    def select_device(self, devices: List[Dict]):
        if not devices:
            print("No devices found.")
            return
        device_list_str = ", ".join(f"{i+1}. {d['dev_id']}" for i, d in enumerate(devices))
        print(f"List of Binded Devices: {device_list_str}")
        try:
            selected_index = 0 # int(input("Please select a device index: ")) - 1
            self.device_id = devices[selected_index]["dev_id"]
            self.get_device_version()
        except (IndexError, ValueError):
            print("Invalid index selected.")

    def get_device_version(self):
        try:
            response = requests.get(f"{self.api_url}/v1/iot-service/api/user/device/version?dev_id={self.device_id}", headers={"authorization": f"Bearer {self.access_token}"})
            response.raise_for_status()
            device_version_info = response.json()
            printer_name, firmware_optional = self.construct_firmware_optional(device_version_info)
            self.compare_and_create_pull_request(printer_name, firmware_optional)
        except requests.RequestException as e:
            print(f"An error occurred while getting the device version: {e}")

    def construct_firmware_optional(self, device_version_info: Dict) -> (str, Dict):
        device_id_map = {
            "00M": "X1C",
            "00W": "X1",
            "01S": "P1P",
            "01P": "P1S",
            "030": "A1_MINI",
            "039": "A1"
        }
        printer_name = next((name for prefix, name in device_id_map.items() if self.device_id.startswith(prefix)), "Unknown")
        
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
        file_path = f"assets/{printer_name}_AMS.json"
        repo = self.github.get_repo(self.repo_name)

        try:
            contents = repo.get_contents(file_path, ref="main")
            old_content = contents.decoded_content.decode("utf-8")
            print(f"new_content: {new_content}")
            print(f"old_content: {old_content}")

            if new_content == old_content:
                print("No changes detected in the firmware optional JSON.")
                return
            else:
                print("Changes detected, creating a pull request.")
        except GithubException:
            print("File does not exist, creating a new one.")

        branch_name = "schedule-update"
        try:
            main_ref = repo.get_git_ref("heads/main")
            repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=main_ref.object.sha)
        except GithubException as e:
            print(f"Error creating branch: {e}")

        try:
            repo.create_file(
                file_path,
                f"Update {printer_name}_AMS JSON file",
                new_content,
                branch=branch_name,
                author=InputGitAuthor(self.author_name, self.author_email)
            )

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
