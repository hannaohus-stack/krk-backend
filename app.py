from flask import Flask, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import os
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# Flask 앱 초기화
app = Flask(__name__)

# CORS 활성화
CORS(app)

# 데이터베이스 설정
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///krk.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

from auth_backend import auth_bp, db

# DB 초기화
db.init_app(app)

# Blueprint 등록
app.register_blueprint(auth_bp)

# 데이터베이스 생성
with app.app_context():
    db.create_all()

@app.route('/health', methods=['GET'])
def health_check():
    """헬스 체크"""
    return jsonify({
        'status': 'ok',
        'service': 'KRK Backend API',
        'version': '1.0.0'
    }), 200

if __name__ == '__main__':
    port = int(os.getenv('FLASK_PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False)
