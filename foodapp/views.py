from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from rest_framework_jwt.settings import api_settings

from .models import Data, UserProfile, ImageModel, Diseasestype, Daily_intake

import base64
import timeit

# YOLO 관련 import
from ultralytics import YOLO
import numpy as np
import cv2

# CLOVA 관련 import
import requests
import uuid
import time
import json

# 원재료명 추출
from konlpy.tag import Okt
import pandas as pd
import re

# Yolo 모델 불러오기
model = YOLO("./yolomodel/best.pt")
from django.db.models import Q

@login_required
def upload_image(request):
    if request.method == 'POST':
        image_file = request.FILES['foodImage']
        start = timeit.default_timer()

        # 이미지를 base64로 변환
        image_content = base64.b64encode(image_file.read()).decode('utf-8')

        # 현재 로그인한 사용자 정보 가져오기
        current_user = request.user  # settings.AUTH_USER_MODEL을 사용하여 현재 프로젝트에서 사용 중인 사용자 모델을 가져옴

        # MongoDB에 저장
        ImageModel.objects.create(user=current_user, image_data=image_content)

        stop = timeit.default_timer()
        print(stop - start)
        return redirect('user:analysis_page')  # 분석 페이지로 이동

    return render(request, 'imageupload.html')

def get_nutrient(input1):
    okt = Okt()
    # 불용어
    stop_words = set(['있습니다', '에', '대한', '다를', '따라','영','양','정보','내','미만','일','영양성분','기','준치','이','므','로','비율','기준','개인','필요','열량','수','다를수있습니다','한','은','의','대'])
    # ocr전처리
    ocr_result = input1
    na_find = ocr_result.find('나')
    gil_find = ocr_result.find('질')
    ocr_result = ocr_result[na_find:gil_find]

    eksdnl_result = re.sub("[^a-z A-Z]",'/',ocr_result)
    eksdnl_list = eksdnl_result.split('/')
    clean_eksdnl = []
    for i in eksdnl_list:
        if i != "":
            clean_eksdnl.append(i)
    eksdnl_df = pd.DataFrame({'단위':clean_eksdnl})

    # 텍스트 전처리
    okt_re = okt.morphs(re.sub("[^가-힣ㄱ-ㅎㅏ-ㅣ]","",ocr_result))
    # 텍스트 불용어 삭제
    clean_okt = [token for token in okt_re if not token in stop_words]
    text_df = pd.DataFrame({"영양성분":clean_okt})
    
    # 숫자 전처리
    re_int = re.sub("[가^-힣ㄱ-ㅎㅏ-ㅣA-Z //s]","/",ocr_result)
    int_list = re_int.split('/')
    clean_int = []
    for i in range(0,len(int_list)):
        if int_list[i] != '':
            clean_int.append(int_list[i])

    # 1차 전처리
    int_df = pd.DataFrame({'함유량':clean_int})
    idx = int_df[int_df['함유량'].str.contains('%','.')].index
    int_df = int_df.drop(idx)
    int_df = int_df.reset_index(drop=True)
    
    # 2자 정리
    idx = int_df[int_df['함유량'].str.contains(',')].index
    for i in idx:
        int_df['함유량'][i] = int_df['함유량'][i].replace(',','')
    int_df = int_df['함유량'].astype('float')

    # 최종 영양성분
    result = pd.concat([text_df,int_df,eksdnl_df],axis=1)
    result = result.dropna()

    return result

def analysis_nutrient(userinfo, input1):
    if input1 == 'end':
        return ''
    else:
        user_profile = UserProfile.objects.get(username=userinfo)
        병 = user_profile.diseases
        if 병 == []:
            gender = user_profile.gender
            age = user_profile.age
            if age >= 20:
                diet = pd.DataFrame(list(Daily_intake.objects.filter(gender=gender,age=20).all().values()))
                return diet.transpose().to_html()
            else:
                diet = pd.DataFrame(list(Daily_intake.objects.filter(gender=gender,age=15).all().values()))
                return diet.transpose().to_html()
        else:
            df = get_nutrient(input1) # 영양정보 비교 할거 
            for i in 병:
                type1 = Diseasestype.objects.filter(병명=i).values('주의사항')
                for tp in type1:
                    array1=tp['주의사항'].split('/')
                    print(array1)
                    주의사항 = array1[0]
                    기준 = float(array1[1])
                    idx = df.index[(df['영양성분']==주의사항)]
                    print(idx) 
                    if float(df.iloc[idx,1]) > 기준:
                        return "{0}에 대한 주의: {1}이(가) 권장량을 초과했습니다.".format(i,주의사항)
                    else:
                        return f"{i}에 대한 주의: {주의사항}이(가) 적정범위 입니다."


def intent(input1):
    if input1 == 'end':
        return '영양성분이 인식되지 않았습니다.'
    else:
        return get_nutrient(input1).to_html()

def analysis_page(request):
    username = request.user

    allergies = get_list(request.user.username)
    blob_data = import_BLOB(username)
    image, cal, materials = detect_label(blob_data)

    retval, buffer = cv2.imencode('.jpg', image)
    img_str = base64.b64encode(buffer).decode()

    content = materials[0:-1]
    found_allergies = []

    # 각 요소에서 allergies에 포함된 성분 찾기
    for item in content:
        for allergy in allergies:
            if allergy in item:
                found_allergies.append(allergy)

    found_allergies = list(set(found_allergies))
    
    try:
        latest_image = ImageModel.objects.filter(user=request.user).order_by('-date').first()
        if latest_image:
            latest_image.allergies_detected = found_allergies
            latest_image.raw_materials = materials[0]
            latest_image.cal_info = cal[0]
            latest_image.save()
    except Exception as e:
        # 에러 처리
        print(f"에러 발생: {str(e)}")

    results = material_result(found_allergies)
    return render(request, 'analysis_page.html', {'image': img_str, 'text': materials[0], 'allergies': found_allergies, 'results': results, 'cal_info': intent(cal[0]),'analysis':analysis_nutrient(username,cal[0])})

def material_result(input):
    results = list()
    for allergy in input:
        data_objects = Data.objects.filter(Q(성분__icontains=allergy)).values('알러지명')
        data_list = list(data_objects)

        # 리스트의 각 딕셔너리에서 '알러지명' 키의 값을 가져와서 출력 형식에 맞게 가공
        result = ', '.join(item['알러지명'] for item in data_list)+'알러지'
        result = allergy + ": "+ result
        results.append(result)
    print(results)
    return results

@login_required
def record(request):
    current_user = request.user
    images = ImageModel.objects.filter(user=current_user).order_by('-date')
    allergies_data = ImageModel.objects.filter(user=current_user).values_list('allergies_detected', flat=True).order_by('-date')
    raw_materials = ImageModel.objects.filter(user=current_user).values_list('raw_materials', flat=True).order_by('-date')
    cal_info = ImageModel.objects.filter(user=current_user).values_list('cal_info', flat=True).order_by('-date')
    allergies_detected_list = list(allergies_data)
    raw_materials = list(raw_materials)
    cal_info = list(cal_info)
    zipped_data = zip(images, allergies_detected_list, raw_materials, cal_info)
    return render(request, 'users/record.html', {'images': images, 'zipped_data': zipped_data})



def login_view(request):
    error_message = None

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        if not username or not password:
            messages.error(request, "아이디와 비밀번호를 모두 입력해주세요.")
            return render(request, "users/login.html")

        user = authenticate(username=username, password=password)

        if user is not None:
            login(request, user)
            # JWT 토큰 생성
            jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER
            jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER

            payload = jwt_payload_handler(user)
            token = jwt_encode_handler(payload)

            print(f"인증 성공, 토큰: {token}")
            return redirect("user:main")

        else:
            print("인증실패")
            error_message = "아이디 또는 비밀번호가 올바르지 않습니다."

    return render(request, "users/login.html", {"error": error_message})

def logout_view(request):
    logout(request)
    return redirect("user:login")

def signup_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        confirm_password = request.POST['confirm_password']
        gender = request.POST['gender']
        age = request.POST['age']
        allergies = request.POST.getlist('allergy[]')
        diseases = request.POST.getlist('disease[]')
        etc = request.POST['etc']

        if password == confirm_password:
            # 사용자 생성 및 추가 정보 저장
            user_profile = UserProfile.objects.create_user(username=username, password=password, email=email, gender=gender, age=age, allergies=allergies, diseases=diseases, etc=etc)

            # 로그인
            authenticated_user = authenticate(request, username=username, password=password)
            
            if authenticated_user:
                login(request, authenticated_user)
                return redirect("user:login")  # 회원가입 후 홈페이지로 리다이렉트
            else:
                # 인증 실패 시 에러 처리
                return render(request, 'users/signup.html', {'error': '사용자 인증에 실패했습니다.'})
        else:
            # 비밀번호 불일치 시 에러 처리
            return render(request, 'users/signup.html', {'error': '비밀번호가 일치하지 않습니다.'})
    else:
        return render(request, 'users/signup.html')
    
@login_required
def update_profile(request):
    if request.method == 'POST':
        gender = request.POST['gender']
        age = request.POST['age']
        allergies = request.POST.getlist('allergy[]')
        diseases = request.POST.getlist('disease[]')
        etc = request.POST['etc']
        password = request.POST['password']
        new_password = request.POST['new-password']
        confirm_password = request.POST['confirm-password']

        # 현재 로그인한 사용자의 정보를 가져옴
        user_profile = request.user

        # 사용자 정보 업데이트
        user_profile.gender = gender
        user_profile.age = age
        user_profile.allergies = allergies
        user_profile.diseases = diseases
        user_profile.etc = etc

        if password and new_password and confirm_password:
            # 사용자가 패스워드를 변경하려는 경우
            if user_profile.check_password(password):
                if new_password == confirm_password:
                    user_profile.set_password(new_password)
                else:
                    return render(request, 'users/update_profile.html', {'error': '새로운 패스워드가 일치하지 않습니다.'})
            else:
                return render(request, 'users/update_profile.html', {'error': '현재 패스워드가 일치하지 않습니다.'})

        user_profile.save()  # 수정된 정보를 저장

        return redirect('user:login')  # 수정 후 리다이렉션할 페이지

    return render(request, 'users/update_profile.html')

def main(request):
    return render(request, 'main.html')

def import_BLOB(username):
    try:
        user = UserProfile.objects.get(username=username)
        latest_image = ImageModel.objects.filter(user=user).order_by('-date').first()
        blob_data = latest_image.image_data
        
        if latest_image:
            return blob_data
        else:
            return None
    except User.DoesNotExist:
        return None
    except Exception as e:
        # 에러 처리
        print(f"에러 발생: {str(e)}")
        return None

def CLOVA_OCR(img):
    api_url = 
    secret_key = 
    request_json = {
        'images': [
            {
                'format': 'jpg',
                'name': 'demo'
            }
        ],
        'requestId': str(uuid.uuid4()),
        'version': 'V2',
        'timestamp': int(round(time.time() * 1000))
    }
    payload = {'message': json.dumps(request_json).encode('UTF-8')}
    files = [
    ('file', cv2.imencode('.png', img)[1].tobytes())
    ]
    headers = {
    'X-OCR-SECRET': secret_key
    }

    response = requests.request("POST", api_url, headers=headers, data = payload, files = files)
    result = response.json()

    text = ""
    for field in result['images'][0]['fields']:
        text += field['inferText']
    return text

def detect_label(blob):
    blob_data = base64.b64decode(blob)
    # 바이너리 데이터를 이미지로 변환
    numpy_array = np.frombuffer(blob_data, np.uint8)
    image = cv2.imdecode(numpy_array, cv2.IMREAD_COLOR)

    cal_info = []
    materials = []

    results = model.predict(image, save=False, imgsz=640, conf=0.5, device='cuda')

    for r in results :
        boxes = r.boxes.xyxy
        cls = r.boxes.cls
        conf = r.boxes.conf
        cls_dict = r.names

        for box, cls_number, conf in zip(boxes, cls, conf) :
            conf_number = float(conf.item())
            cls_number_int = int(cls_number.item())
            cls_name = cls_dict[cls_number_int]
            x1, y1, x2, y2 = box
            x1_int = int(x1.item())
            y1_int = int(y1.item())
            x2_int = int(x2.item())
            y2_int = int(y2.item())

            if cls_name == 'cal_info':
                image = cv2.rectangle(image, (x1_int, y1_int), (x2_int, y2_int), (255,0,0), 2)
                cropped_image = image[y1_int:y2_int, x1_int:x2_int]
                image_mat = cv2.UMat(cropped_image)
                cal_info.append(CLOVA_OCR(image_mat))
            if cls_name == 'material':
                image = cv2.rectangle(image, (x1_int, y1_int), (x2_int, y2_int), (255,0,0), 2)
                cropped_image = image[y1_int:y2_int, x1_int:x2_int]
                image_mat = cv2.UMat(cropped_image)
                materials.append(CLOVA_OCR(image_mat))
        cal_info.append('en\\d')
        materials.append('end')
        return image, cal_info, materials


def get_list(userinfo):
    # UserProfile에서 해당 사용자의 알러지 정보 불러오기
    user_profile = UserProfile.objects.get(username=userinfo)
    allergen = user_profile.allergies
    allergens = user_profile.allergies if user_profile.allergies else []
    
    # 알러지성분에 해당하는 원재료명 리스트로 저장
    data_list = []

    for allergen in allergens:
        data_objects = Data.objects.filter(알러지명=allergen).values('성분')
        for obj in data_objects:
            ingredients = obj['성분'].split(sep=",")
            data_list.extend(ingredients)

    # 중복 제거를 위해 set으로 변환 후 다시 list로 변환
    data_list = list(set(data_list))
    
    return data_list


