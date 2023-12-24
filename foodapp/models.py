from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.db import models
from datetime import datetime

class ImageModel(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    image_data = models.TextField()
    date = models.DateTimeField(default=datetime.now)
    username = models.CharField(max_length=150, blank=True, null=True)
    allergies_detected = models.TextField(blank=True, null=True)  # 추가된 부분
    raw_materials = models.TextField()
    cal_info = models.TextField()

    def save(self, *args, **kwargs):
        # user가 설정되어 있으면 username 필드에 해당하는 값을 저장
        if self.user:
            self.username = self.user.username
        super().save(*args, **kwargs)

    class Meta:
        db_table = 'imagecollection'


class UserProfile(AbstractUser):
    # 기존 User 모델에서 상속받아 사용
    email = models.EmailField(unique=True)
    gender = models.CharField(max_length=10)
    age = models.IntegerField()
    allergies = models.JSONField(default=list)
    diseases = models.JSONField(default=list)
    etc = models.TextField()

    def __str__(self):
        return self.username        
    
    class Meta:
        db_table = 'users_user'

class Data(models.Model):
    알러지명 = models.CharField(max_length=50, blank=False, default='')
    성분 = models.JSONField(default=list)

    class Meta:
        db_table = 'foodcollection'

class Diseasestype(models.Model):
    id = models.IntegerField(primary_key=True)
    병명 = models.CharField(max_length=50,blank=False, default='')
    주의사항 = models.JSONField(default=dict)

    class Meta:
        db_table = 'Diseasescollection'

class Daily_intake(models.Model):
    gender = models.CharField(max_length=50,blank=False, default='')
    age = models.IntegerField()
    탄수화물 = models.IntegerField()
    단백질 = models.IntegerField()
    지방 = models.IntegerField()
    나트륨 = models.IntegerField()
    당류 = models.IntegerField()

    class Meta:
        db_table='Daily_intake'