import json
import os

CONFIG_FILE = 'config.json'

def load_config():
    """설정 파일에서 API 키와 파일 경로를 불러옵니다."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            # 파일 내용이 깨졌을 경우 초기 설정 반환
            return { 'tesseract_path': '', 'deepl_api_key': '' }
    return {
        'tesseract_path': '',
        'deepl_api_key': ''
    }

def save_config(config_data):
    """현재 설정을 파일에 저장합니다."""
    # 딕셔너리가 아닌 다른 타입이 들어올 경우를 대비한 검증은 생략합니다.
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config_data, f, indent=4)

# 프로그램 시작 시 설정 불러오기
CONFIG = load_config()

def get_tesseract_path():
    return CONFIG.get('tesseract_path', '')

def get_deepl_key():
    return CONFIG.get('deepl_api_key', '')