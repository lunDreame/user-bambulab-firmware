import os
import requests
import json


class JsonUpdater:
    def __init__(self, file_path):
        self.file_path = file_path

    def load_json(self):
        try:
            with open(self.file_path, "r", encoding="utf-8") as file:
                return json.load(file)
        except FileNotFoundError:
            print(f"{self.file_path} 파일을 찾을 수 없습니다.")
            return None

    def update_firmware_info(self, version, url, description):
        data = self.load_json()
        if data is None:
            return

        try:
            data["upgrade"]["firmware_optional"]["firmware"]["version"] = version
            data["upgrade"]["firmware_optional"]["firmware"]["url"] = url
            data["upgrade"]["firmware_optional"]["firmware"]["description"] = description

            with open(self.file_path, "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=4)

            print(f"{self.file_path} 파일이 성공적으로 업데이트되었습니다.")
        except KeyError as e:
            print(f"키 {e}를 찾을 수 없습니다.")


class FetchFirmwarePayload:
    def __init__(self):
        # ENV
        self.account = os.getenv("BAMBU_ACCOUNT")
        self.password = os.getenv("BAMBU_PASSWORD")
        
        self.base_login = "https://bambulab.com/api/sign-in/form"
        self.api_bambulab = "https://api.bambulab.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        self.device_id: str | None = None
        self.access_token: str | None = None

        self.login_bambulab()

    def mask_serial(self, serial: str) -> str:
        if not serial:
            return "N/A"
        return f"{serial[:4]}{'*' * (len(serial) - 4)}"

    def login_bambulab(self):
        try:
            response = requests.post(
                self.base_login, 
                headers=self.headers,
                data={"account": self.account, "password": self.password}
            )
            response.raise_for_status()
            self.access_token = response.cookies.get("token", "")
            if response.status_code == 200 and not response.json().get("tfaKey"):
                print("[+] Login Successful")
                self.get_binded_devices()
            else:
                print("[-] Login Failed")
        except requests.RequestException as e:
            print(f"[-] Error during login: {e}")

    def get_binded_devices(self):
        headers = {
            **self.headers,
            "authorization": f"Bearer {self.access_token}"
        }
        try:
            response = requests.get(
                f"{self.api_bambulab}/v1/iot-service/api/user/bind", 
                headers=headers
            )
            response.raise_for_status()
            devices = response.json().get("devices", [])
            self.select_device(devices)
        except requests.RequestException as e:
            print(f"[-] Error getting devices: {e}")

    def select_device(self, devices: list[dict]):
        if not devices:
            print("[-] No devices found")
            return
        try:
            selected_index = 0  # P1P
            selected_device = devices[selected_index]
            self.device_id = selected_device["dev_id"]
            
            dev_product_name = selected_device["dev_model_name"]
            self.extract_firmware_payload(dev_product_name)
        except (IndexError, ValueError) as e:
            print(f"[-] Invalid device selection: {e}")

    def extract_firmware_payload(self, product_name: str):
        headers = {
            **self.headers,
            "authorization": f"Bearer {self.access_token}"
        }
        try:
            response = requests.get(
                f"{self.api_bambulab}/v1/iot-service/api/user/device/version?dev_id={self.device_id}", 
                headers=headers
            )
            response.raise_for_status()
            device_version_info = response.json()
            
            devices = device_version_info.get("devices", [])
            if devices:
                device = devices[0]
                
                if product_name == "P1P":
                    for i, p_name in enumerate(["P1P", "P1S"]):
                        updater = JsonUpdater(f"../assets/{p_name}_AMS.json")
                        updater.update_firmware_info(
                            version=device["firmware"]["version"], 
                            url=device["firmware"]["url"].replace("C11", f"C1{i + 1}"), 
                            description=device["firmware"]["description"]
                        )
                else:
                    updater = JsonUpdater(f"../assets/{product_name}_AMS.json")
                    updater.update_firmware_info(
                        version=device["firmware"]["version"], 
                        url=device["firmware"]["url"], 
                        description=device["firmware"]["description"]
                    )
        except requests.RequestException as e:
            print(f"[-] Error getting version info: {e}")


if __name__ == "__main__":
    FetchFirmwarePayload()
