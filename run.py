#!/usr/bin/env python
"""
K-Law Assistant 실행 스크립트
간편한 실행과 환경 체크를 제공합니다.
"""

import os
import sys
import subprocess
from pathlib import Path

def check_environment():
    """환경 체크"""
    print("🔍 환경 체크 중...")
    
    # Python 버전 체크
    python_version = sys.version_info
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 8):
        print("❌ Python 3.8 이상이 필요합니다.")
        return False
    print(f"✅ Python {python_version.major}.{python_version.minor}.{python_version.micro}")
    
    # .env 파일 체크
    env_file = Path(".env")
    if not env_file.exists():
        print("⚠️ .env 파일이 없습니다. .env.example을 복사하여 생성하세요.")
        
        # .env.example 복사 제안
        if Path(".env.example").exists():
            response = input("📋 .env.example을 .env로 복사할까요? (y/n): ")
            if response.lower() == 'y':
                import shutil
                shutil.copy(".env.example", ".env")
                print("✅ .env 파일이 생성되었습니다. API 키를 입력해주세요.")
            return False
    else:
        print("✅ .env 파일 확인")
    
    # 필수 패키지 체크
    try:
        import streamlit
        print("✅ Streamlit 설치 확인")
    except ImportError:
        print("❌ Streamlit이 설치되지 않았습니다.")
        print("💡 pip install -r requirements.txt 를 실행하세요.")
        return False
    
    # API 키 체크
    from dotenv import load_dotenv
    load_dotenv()
    
    law_api_key = os.getenv('LAW_API_KEY')
    openai_api_key = os.getenv('OPENAI_API_KEY')
    
    if not law_api_key or law_api_key == 'your_law_api_key_here':
        print("⚠️ 법제처 API 키가 설정되지 않았습니다.")
        print("💡 https://open.law.go.kr 에서 API 키를 발급받아 .env 파일에 입력하세요.")
    else:
        print("✅ 법제처 API 키 확인")
    
    if not openai_api_key or openai_api_key.startswith('sk-your'):
        print("⚠️ OpenAI API 키가 설정되지 않았습니다.")
        print("💡 https://platform.openai.com 에서 API 키를 발급받아 .env 파일에 입력하세요.")
    else:
        print("✅ OpenAI API 키 확인")
    
    return True

def install_requirements():
    """패키지 설치"""
    print("\n📦 필요한 패키지를 설치합니다...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ 패키지 설치 완료")
        return True
    except subprocess.CalledProcessError:
        print("❌ 패키지 설치 실패")
        return False

def run_app():
    """Streamlit 앱 실행"""
    print("\n🚀 K-Law Assistant를 시작합니다...")
    print("=" * 50)
    print("⚖️  K-Law Assistant - AI 법률 검토 지원 시스템")
    print("=" * 50)
    print("\n브라우저가 자동으로 열립니다.")
    print("수동으로 접속하려면: http://localhost:8501")
    print("\n종료하려면 Ctrl+C를 누르세요.")
    print("-" * 50)
    
    try:
        subprocess.run(["streamlit", "run", "main.py"])
    except KeyboardInterrupt:
        print("\n\n👋 K-Law Assistant를 종료합니다.")
    except Exception as e:
        print(f"\n❌ 실행 중 오류 발생: {e}")

def main():
    """메인 함수"""
    print("=" * 50)
    print("⚖️  K-Law Assistant 실행 준비")
    print("=" * 50)
    
    # 환경 체크
    if not check_environment():
        print("\n⚠️ 환경 설정이 필요합니다.")
        
        # 패키지 설치 제안
        response = input("\n📦 필요한 패키지를 설치할까요? (y/n): ")
        if response.lower() == 'y':
            if install_requirements():
                print("\n✅ 설치 완료! 다시 실행해주세요.")
            else:
                print("\n❌ 설치 실패. requirements.txt를 확인해주세요.")
        return
    
    # 앱 실행
    print("\n✅ 모든 준비가 완료되었습니다!")
    response = input("\n🚀 K-Law Assistant를 시작할까요? (y/n): ")
    
    if response.lower() == 'y':
        run_app()
    else:
        print("👋 다음에 만나요!")

if __name__ == "__main__":
    main()