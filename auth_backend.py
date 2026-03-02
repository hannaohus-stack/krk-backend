“””
KRK Backend - User Authentication
File: auth_backend.py

Flask 기반 Kakao 간편 로그인 구현
포함된 내용:

1. User 데이터베이스 모델
1. Kakao 인증 라우트
1. JWT 토큰 관리
1. 사용자 정보 조회
   “””

import os
import jwt
from datetime import datetime, timedelta
from functools import wraps
from flask import Blueprint, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
import requests

# 환경 변수 로드

load_dotenv()

# ===== 데이터베이스 설정 =====

db = SQLAlchemy()

# ===== User 모델 =====

class User(db.Model):
“”“사용자 정보 모델”””
**tablename** = ‘users’

```
# 기본 정보
id = db.Column(db.Integer, primary_key=True)
kakao_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
email = db.Column(db.String(120), unique=True, nullable=True, index=True)
nickname = db.Column(db.String(120), nullable=False)
profile_image_url = db.Column(db.String(500), nullable=True)

# 비즈니스 정보
company_name = db.Column(db.String(200), nullable=True)
business_registration_number = db.Column(db.String(50), nullable=True)

# 플랜 정보
plan = db.Column(db.String(20), default='LITE')  # LITE, STANDARD, PREMIUM
status = db.Column(db.String(20), default='active')  # active, suspended, deleted

# 메타데이터
created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
last_login_at = db.Column(db.DateTime, nullable=True)
updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# 관리자 정보
notes = db.Column(db.Text, nullable=True)  # 관리자 메모

def to_dict(self):
    """사용자 정보를 JSON으로 변환"""
    return {
        'id': self.id,
        'kakao_id': self.kakao_id,
        'email': self.email,
        'nickname': self.nickname,
        'profile_image_url': self.profile_image_url,
        'company_name': self.company_name,
        'plan': self.plan,
        'status': self.status,
        'created_at': self.created_at.isoformat() if self.created_at else None,
        'last_login_at': self.last_login_at.isoformat() if self.last_login_at else None
    }

def __repr__(self):
    return f'<User {self.nickname} ({self.kakao_id})>'
```

# ===== 인증 Blueprint =====

auth_bp = Blueprint(‘auth’, **name**, url_prefix=’/api/auth’)

# 환경 변수

KAKAO_REST_API_KEY = os.getenv(‘KAKAO_REST_API_KEY’)
JWT_SECRET = os.getenv(‘JWT_SECRET_KEY’, ‘dev-secret-key-change-in-production’)
JWT_ALGORITHM = os.getenv(‘JWT_ALGORITHM’, ‘HS256’)
JWT_EXPIRY_DAYS = int(os.getenv(‘JWT_EXPIRY_DAYS’, ‘30’))

# ===== JWT 토큰 관리 함수 =====

def generate_jwt_token(user_id, expires_in_days=None):
“””
JWT 토큰 생성

```
Args:
    user_id (int): 사용자 ID
    expires_in_days (int): 만료 기간 (기본값: 30일)

Returns:
    str: JWT 토큰
"""
if expires_in_days is None:
    expires_in_days = JWT_EXPIRY_DAYS

payload = {
    'user_id': user_id,
    'iat': datetime.utcnow(),
    'exp': datetime.utcnow() + timedelta(days=expires_in_days),
    'type': 'access'
}

token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
return token
```

def verify_jwt_token(token):
“””
JWT 토큰 검증

```
Args:
    token (str): JWT 토큰

Returns:
    dict: 토큰 페이로드, 또는 None (검증 실패)
"""
try:
    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    return payload
except jwt.ExpiredSignatureError:
    return None
except jwt.InvalidTokenError:
    return None
```

def token_required(f):
“””
토큰 검증 데코레이터

```
Authorization 헤더에서 토큰을 추출하고 검증합니다.
검증 성공 시 current_user를 함수에 전달합니다.
"""
@wraps(f)
def decorated(*args, **kwargs):
    token = None
    
    # 1. Authorization 헤더에서 토큰 추출
    if 'Authorization' in request.headers:
        auth_header = request.headers['Authorization']
        try:
            # "Bearer TOKEN" 형식에서 토큰 추출
            token = auth_header.split(" ")[1]
        except IndexError:
            return jsonify({'error': '유효하지 않은 토큰 형식'}), 401
    
    if not token:
        return jsonify({'error': '토큰이 필요합니다'}), 401
    
    # 2. 토큰 검증
    payload = verify_jwt_token(token)
    if not payload:
        return jsonify({'error': '유효하지 않은 또는 만료된 토큰'}), 401
    
    # 3. 사용자 조회
    user_id = payload.get('user_id')
    current_user = User.query.get(user_id)
    
    if not current_user:
        return jsonify({'error': '사용자를 찾을 수 없습니다'}), 404
    
    # 4. 계정 상태 확인
    if current_user.status != 'active':
        return jsonify({'error': '비활성화된 계정입니다'}), 403
    
    return f(current_user, *args, **kwargs)

return decorated
```

# ===== Kakao 인증 라우트 =====

@auth_bp.route(’/kakao’, methods=[‘POST’])
def kakao_login():
“””
Kakao 간편 로그인 처리

```
프론트엔드에서 Kakao SDK로 획득한 사용자 정보를 받아
데이터베이스에 저장하고 JWT 토큰을 발급합니다.

Request Body:
{
    "kakaoId": "123456789",
    "nickname": "사용자닉네임",
    "email": "user@example.com",
    "profileImageUrl": "https://..."
}

Response:
{
    "token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "user": { ... }
}
"""
try:
    # 1. 요청 데이터 추출
    data = request.get_json()
    
    kakao_id = data.get('kakaoId')
    email = data.get('email')
    nickname = data.get('nickname')
    profile_image_url = data.get('profileImageUrl')
    
    # 2. 필수 정보 검증
    if not kakao_id or not nickname:
        return jsonify({'error': '필수 정보가 누락되었습니다'}), 400
    
    print(f"[Kakao Login] 처리 중: {kakao_id} - {nickname}")
    
    # 3. 기존 사용자 조회
    user = User.query.filter_by(kakao_id=kakao_id).first()
    
    if user:
        # 기존 사용자: 정보 업데이트 및 마지막 로그인 시간 기록
        print(f"[Kakao Login] 기존 사용자: {user.id}")
        
        if email and not user.email:
            user.email = email
        if profile_image_url:
            user.profile_image_url = profile_image_url
        
        user.last_login_at = datetime.utcnow()
    else:
        # 신규 사용자: 생성
        print(f"[Kakao Login] 신규 사용자 생성: {kakao_id}")
        
        user = User(
            kakao_id=kakao_id,
            email=email,
            nickname=nickname,
            profile_image_url=profile_image_url,
            plan='LITE',  # 기본값
            status='active',
            last_login_at=datetime.utcnow()
        )
        db.session.add(user)
    
    # 4. 데이터베이스 저장
    db.session.commit()
    print(f"[Kakao Login] 사용자 저장 완료: {user.id}")
    
    # 5. JWT 토큰 생성
    token = generate_jwt_token(user.id)
    
    # 6. 응답
    return jsonify({
        'token': token,
        'user': user.to_dict(),
        'message': '로그인 성공'
    }), 200
    
except Exception as e:
    db.session.rollback()
    print(f"[Kakao Login] 에러: {str(e)}")
    return jsonify({'error': '로그인 처리 중 오류가 발생했습니다'}), 500
```

@auth_bp.route(’/kakao/token-refresh’, methods=[‘POST’])
@token_required
def refresh_token(current_user):
“””
토큰 갱신

```
기존 토큰이 만료되기 전에 새로운 토큰을 발급합니다.
"""
new_token = generate_jwt_token(current_user.id)
return jsonify({
    'token': new_token,
    'message': '토큰이 갱신되었습니다'
}), 200
```

# ===== 사용자 정보 조회 라우트 =====

@auth_bp.route(’/me’, methods=[‘GET’])
@token_required
def get_current_user(current_user):
“””
현재 로그인한 사용자 정보 조회

```
Header:
    Authorization: Bearer <token>

Response:
    { 사용자 정보 }
"""
return jsonify(current_user.to_dict()), 200
```

@auth_bp.route(’/me/profile’, methods=[‘PUT’])
@token_required
def update_user_profile(current_user):
“””
사용자 프로필 정보 업데이트

```
Request Body:
{
    "nickname": "새로운닉네임",
    "company_name": "회사명",
    "business_registration_number": "사업자번호"
}
"""
try:
    data = request.get_json()
    
    if 'nickname' in data:
        current_user.nickname = data['nickname']
    if 'company_name' in data:
        current_user.company_name = data['company_name']
    if 'business_registration_number' in data:
        current_user.business_registration_number = data['business_registration_number']
    
    db.session.commit()
    print(f"[Profile Update] 사용자 {current_user.id} 프로필 업데이트")
    
    return jsonify({
        'user': current_user.to_dict(),
        'message': '프로필이 업데이트되었습니다'
    }), 200
    
except Exception as e:
    db.session.rollback()
    print(f"[Profile Update] 에러: {str(e)}")
    return jsonify({'error': '프로필 업데이트 중 오류가 발생했습니다'}), 500
```

# ===== 로그아웃 라우트 =====

@auth_bp.route(’/logout’, methods=[‘POST’])
@token_required
def logout(current_user):
“””
로그아웃 처리

```
프론트엔드에서 로컬스토리지의 토큰을 삭제합니다.
백엔드에서는 로그아웃 기록만 남깁니다 (선택사항).
"""
print(f"[Logout] 사용자 {current_user.id} 로그아웃")

return jsonify({
    'message': '로그아웃되었습니다'
}), 200
```

# ===== 헬스 체크 라우트 =====

@auth_bp.route(’/health’, methods=[‘GET’])
def health_check():
“””
인증 시스템 헬스 체크
“””
return jsonify({
‘status’: ‘healthy’,
‘service’: ‘Kakao Authentication API’
}), 200

# ===== 에러 핸들러 =====

@auth_bp.errorhandler(400)
def bad_request(error):
return jsonify({‘error’: ‘잘못된 요청입니다’}), 400

@auth_bp.errorhandler(401)
def unauthorized(error):
return jsonify({‘error’: ‘인증이 필요합니다’}), 401

@auth_bp.errorhandler(404)
def not_found(error):
return jsonify({‘error’: ‘요청한 자원을 찾을 수 없습니다’}), 404

@auth_bp.errorhandler(500)
def internal_error(error):
db.session.rollback()
return jsonify({‘error’: ‘서버 오류가 발생했습니다’}), 500

# ===== Flask 앱에서 사용하는 방법 =====

“””

# app.py

from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(**name**)

# 데이터베이스 설정

app.config[‘SQLALCHEMY_DATABASE_URI’] = os.getenv(‘DATABASE_URL’, ‘sqlite:///krk.db’)
app.config[‘SQLALCHEMY_TRACK_MODIFICATIONS’] = False
app.config[‘SECRET_KEY’] = os.getenv(‘JWT_SECRET_KEY’, ‘dev-key’)

# CORS 활성화

CORS(app)

# DB 초기화

from auth_backend import db
db.init_app(app)

# 인증 라우트 등록

from auth_backend import auth_bp
app.register_blueprint(auth_bp)

# 데이터베이스 생성

with app.app_context():
db.create_all()

if **name** == ‘**main**’:
app.run(debug=True, port=5000)
“””
