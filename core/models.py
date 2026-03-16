from django.contrib.auth.models import User
from django.db import models

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=20, null=True, blank=True)
    blood_group = models.CharField(max_length=5, blank=True, null=True)

    allergies = models.TextField(null=True, blank=True)
    medical_conditions = models.TextField(null=True, blank=True)
    current_medications = models.TextField(null=True, blank=True)
    
    # Scan tracking
    scan_count = models.IntegerField(default=0)
    risk_count = models.IntegerField(default=0)

    def __str__(self):
        return self.user.username


class Medicine(models.Model):
    name = models.CharField(max_length=200)
    manufacturer = models.CharField(max_length=200)
    batch_number = models.CharField(max_length=100)
    expiry_date = models.DateField()
    description = models.TextField()
    side_effects = models.TextField()

    def __str__(self):
        return self.name
class MedicineUpload(models.Model):
    image = models.ImageField(upload_to='medicine_images/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Upload {self.id}"


class ScanHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='scan_history')
    medicine_name = models.CharField(max_length=200, null=True, blank=True)
    authenticity = models.CharField(max_length=50, null=True, blank=True)
    authenticity_confidence = models.FloatField(null=True, blank=True)
    risk_level = models.CharField(max_length=50, null=True, blank=True)
    scan_date = models.DateTimeField(auto_now_add=True)
    image_url = models.CharField(max_length=500, null=True, blank=True)
    
    class Meta:
        ordering = ['-scan_date']  # Most recent scans first
    
    def __str__(self):
        return f"{self.user.username} - {self.medicine_name} - {self.scan_date.strftime('%Y-%m-%d %H:%M')}"
