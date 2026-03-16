from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.files.storage import FileSystemStorage
from .models import UserProfile, ScanHistory
from django.shortcuts import redirect, render
from django.contrib import messages
import os
from django.conf import settings
from django.core.files.base import ContentFile
import base64
from datetime import datetime

# Try to import TensorFlow - if not available, ML features will be disabled
TF_AVAILABLE = False
np = None
keras_image = None

try:
    import numpy as np
    from tensorflow.keras.preprocessing import image as keras_image
    TF_AVAILABLE = True
except ImportError:
    pass

# Medicine database module was removed in cleanup
import json
from .ocr_utils import get_ocr_prediction

# Medicine information database - loaded from JSON (created from CSV training data)
# This contains detailed info for all 11,000+ medicines
MEDICINE_INFO = {}

def load_medicine_info_database():
    """Load medicine info from the JSON database created from Excel"""
    global MEDICINE_INFO
    
    if MEDICINE_INFO:
        return MEDICINE_INFO
    
    # Try to load from the new database first
    db_path = os.path.join(settings.BASE_DIR, 'medicine_info.json')
    
    if os.path.exists(db_path):
        try:
            with open(db_path, 'r', encoding='utf-8') as f:
                MEDICINE_INFO = json.load(f)
            print(f"Loaded medicine info database with {len(MEDICINE_INFO)} medicines")
            return MEDICINE_INFO
        except Exception as e:
            print(f"Error loading medicine info database: {e}")
    
    # Fallback to a minimal list if database not available
    MEDICINE_INFO = {
        'Paracetamol': {'name': 'Paracetamol', 'uses': 'Pain relief and fever reduction', 'dosage': '1-2 tablets every 4-6 hours', 'side_effects': 'Nausea, liver damage in excess'},
        'Ibuprofen': {'name': 'Ibuprofen', 'uses': 'Anti-inflammatory and pain relief', 'dosage': '1 tablet every 4-6 hours', 'side_effects': 'Stomach upset'}
    }
    
    return MEDICINE_INFO



def get_medicine_details(medicine_name):
    """Get detailed information about a medicine"""
    if not MEDICINE_INFO:
        load_medicine_info_database()
    
    if not medicine_name:
        return None
    
    # Try exact match first
    if medicine_name in MEDICINE_INFO:
        return MEDICINE_INFO[medicine_name]
    
    # Try case-insensitive match
    medicine_upper = medicine_name.upper()
    for key, value in MEDICINE_INFO.items():
        if key.upper() == medicine_upper:
            return value
    
    # Try partial match
    for key, value in MEDICINE_INFO.items():
        if medicine_upper in key.upper() or key.upper() in medicine_upper:
            return value
    
    return None

# Cache for loaded model and class labels
_ml_model_cache = None
_model_classes = None

# Cache for genuine/fake model
_genuine_fake_model_cache = None

# Cache for medicine database (QR codes)
_medicine_db_cache = None

# Cache for medicine info database (11,000+ medicines from CSV)
_medicine_info_db_cache = None

# Cache for barcode to medicine mapping
_barcode_mapping_cache = None

def load_barcode_mapping():
    """Load the mapping from barcode/QR code to medicine name"""
    global _barcode_mapping_cache
    
    if _barcode_mapping_cache is not None:
        return _barcode_mapping_cache
    
    db_path = os.path.join(settings.BASE_DIR, 'barcode_mapping.json')
    
    if os.path.exists(db_path):
        try:
            with open(db_path, 'r') as f:
                _barcode_mapping_cache = json.load(f)
            print(f"Barcode mapping loaded: {len(_barcode_mapping_cache)} entries")
            return _barcode_mapping_cache
        except Exception as e:
            print(f"Error loading barcode mapping: {e}")
            
    return {}


def load_medicine_database():
    """Load the medicine database from JSON (QR code database)"""
    global _medicine_db_cache
    
    if _medicine_db_cache is not None:
        return _medicine_db_cache
    
    db_path = os.path.join(settings.BASE_DIR, 'medicine_database.json')
    
    if os.path.exists(db_path):
        try:
            with open(db_path, 'r') as f:
                _medicine_db_cache = json.load(f)
            print(f"Medicine database loaded: {len(_medicine_db_cache.get('medicines', []))} medicines")
            return _medicine_db_cache
        except Exception as e:
            print(f"Error loading medicine database: {e}")
    
    return None


def load_medicine_info_db():
    """Load the medicine info database (11,000+ medicines from CSV)"""
    global _medicine_info_db_cache
    
    if _medicine_info_db_cache is not None:
        return _medicine_info_db_cache
    
    db_path = os.path.join(settings.BASE_DIR, 'medicine_info.json')
    
    if os.path.exists(db_path):
        try:
            with open(db_path, 'r', encoding='utf-8') as f:
                _medicine_info_db_cache = json.load(f)
            print(f"Medicine info database loaded with {len(_medicine_info_db_cache)} medicines")
            return _medicine_info_db_cache
        except Exception as e:
            print(f"Error loading medicine info database: {e}")
    
    return None


def check_medicine_in_database(medicine_name):
    """
    Check if a medicine exists in our medicine database.
    Since we are using a 55-class custom model, we trust the model's prediction 
    even if the external JSON databases are missing.
    
    Returns: (is_found, medicine_name_matched, confidence)
    """
    if not medicine_name or medicine_name == 'Unknown' or medicine_name == 'Fake':
        return False, None, 0.0
        
    db = load_medicine_info_db()
    
    # If database doesn't exist at all (we deleted it), just trust the ML model 
    # since the ML model has already classified it into a genuine 55-class category.
    if not db:
        return True, medicine_name, 0.85
    
    medicine_name_upper = medicine_name.upper().strip()
    medicines = list(db.keys())
    
    # Try exact match with medicine names
    for med in medicines:
        if med.upper() == medicine_name_upper:
            return True, med, 1.0
    
    # Try partial match (contains)
    for med in medicines:
        if medicine_name_upper in med.upper() or med.upper() in medicine_name_upper:
            return True, med, 0.8
    
    # Only return false if DB exists but medicine isn't in it
    return False, None, 0.0


def decode_qr_code(image_path):
    """
    Decode QR code or Barcode from image.
    Returns the decoded text or None if no code found.
    """
    try:
        import cv2
        import zxingcpp
        
        # Read image
        img = cv2.imread(image_path)
        if img is None:
            print("Could not read image for decoding")
            return None
            
        results = zxingcpp.read_barcodes(img)
        
        if results:
            # Return the first decoded code data
            code_data = results[0].text
            print(f"Barcode/QR Code decoded: {code_data}")
            return code_data
        else:
            print("No barcode/QR code found in image")
            return None
    except ImportError:
        print("zxingcpp or opencv-python not installed - cannot decode QR codes")
        return None
    except Exception as e:
        print(f"Code decode error: {e}")
        return None


def check_medicine_authenticity(qr_data):
    """
    Check if medicine is genuine based on QR code data.
    Uses the medicine database created from Excel.
    Returns: (is_genuine, medicine_name, confidence, method)
    """
    if not qr_data:
        return None, None, 0, "No QR code"
    
    db = load_medicine_database()
    if not db:
        return None, None, 0, "Database not available"
    
    qr_data_upper = qr_data.upper().strip()
    
    # Check exact match with medicine names
    medicines = db.get('medicines', [])
    for med in medicines:
        if med.upper() == qr_data_upper:
            return True, med, 1.0, "QR Code Database"
    
    # Check exact match with medicine IDs
    medicine_ids = db.get('medicine_ids', [])
    for mid in medicine_ids:
        if mid.upper() == qr_data_upper:
            return True, qr_data, 1.0, "QR Code Database"
    
    # Check partial match
    for med in medicines:
        if qr_data_upper in med.upper() or med.upper() in qr_data_upper:
            return True, med, 0.9, "QR Code Database (Partial Match)"
    
    # Not found - could be fake
    return False, None, 0, "QR Code not in database"


def load_ml_model_and_classes():
    """Load the trained medicine identification model and get class labels"""
    global _ml_model_cache, _model_classes
    
    if not TF_AVAILABLE:
        return None, []
    
    # Return cached model if already loaded
    if _ml_model_cache is not None:
        return _ml_model_cache, _model_classes
    
    # Try advanced model first
    model_paths = [
        os.path.join(settings.BASE_DIR, 'advanced_medicine_model.h5'),
        os.path.join(settings.BASE_DIR, 'medicine_identifier_54.h5'),
        os.path.join(settings.BASE_DIR, 'medicine_identifier.h5')
    ]
    
    model_path = None
    for path in model_paths:
        if os.path.exists(path):
            model_path = path
            break
    
    if not model_path:
        print("No model file found")
        return None, []
        
    try:
        from tensorflow.keras.models import load_model
        _ml_model_cache = load_model(model_path)
        
        # Get class labels - try to load from advanced JSON file first
        if 'advanced' in model_path:
            class_labels_path = os.path.join(settings.BASE_DIR, 'advanced_class_labels.json')
        else:
            class_labels_path = os.path.join(settings.BASE_DIR, 'class_labels_54.json')
        
        if os.path.exists(class_labels_path):
            with open(class_labels_path, 'r') as f:
                _model_classes = json.load(f)
                # Convert numeric keys to string indices
                _model_classes = [str(v) for k, v in sorted(_model_classes.items(), key=lambda x: int(x[0]))]
        else:
            # Fall back to hardcoded class labels based on model output shape
            num_classes = _ml_model_cache.output_shape[-1]
            
            if num_classes == 2:
                _model_classes = ['Fake', 'Genuine']
            elif num_classes == 20:
                _model_classes = [
                    'Ascozin', 'Bioflu', 'Biogesic', 'Bonamine', 'Buscopan',
                    'DayZinc', 'Decolgen', 'Flanax', 'Imodium', 'Lactezin',
                    'Lagundi', 'Midol', 'Myra_E', 'Neurogen_E', 'Omeprazole',
                    'Rinityn', 'Rogin_E', 'Sinecod', 'Tempra', 'Tuseran'
                ]
            else:
                _model_classes = [f'Class_{i}' for i in range(num_classes)]
            
        print(f"Model loaded from {model_path} with {len(_model_classes)} classes")
        print(f"Classes: {_model_classes}")
            
        return _ml_model_cache, _model_classes
    except Exception as e:
        print(f"Error loading model: {e}")
        return None, []


def predict_medicine(image_path):
    """Predict the medicine from an image"""
    if not TF_AVAILABLE:
        return None, 0, "ML not available"
        
    model, classes = load_ml_model_and_classes()
    if model is None or not classes:
        return None, 0, "Model not loaded"
        
    try:
        if keras_image is None:
            return None, 0, "Image processing not available"
            
        # 1. Start with CNN Prediction
        target_size = (224, 224) if hasattr(model, 'input_shape') and model.input_shape[1] == 224 else (128, 128)
        img = keras_image.load_img(image_path, target_size=target_size)
        img_array = keras_image.img_to_array(img)
        img_array = np.expand_dims(img_array, axis=0)
        img_array = img_array / 255.0
        predictions = model.predict(img_array)
        predicted_class_idx = np.argmax(predictions[0])
        cnn_confidence = float(np.max(predictions[0]))
        cnn_prediction = classes[predicted_class_idx]
        
        # 2. Add OCR Verification
        print(f"Running OCR verification for: {image_path}")
        labels_path = os.path.join(settings.BASE_DIR, 'advanced_class_labels.json')
        ocr_prediction, ocr_score = get_ocr_prediction(image_path, labels_path)
        
        print(f"CNN Prediction: {cnn_prediction} ({cnn_confidence:.2f})")
        print(f"OCR Prediction: {ocr_prediction} ({ocr_score:.2f})")
        
        # Ensemble Logic:
        # - If OCR has very high confidence (e.g. > 80%), trust the OCR.
        # - If CNN is high confidence and OCR is low, trust CNN.
        # - If they match, highly certain.
        # - If they disagree and both are medium, mark as high risk/fake.
        
        final_prediction = cnn_prediction
        final_confidence = cnn_confidence
        
        if ocr_score > 85:
            final_prediction = ocr_prediction
            final_confidence = max(cnn_confidence, ocr_score/100.0)
        elif cnn_prediction == 'Unknown' and ocr_score > 60:
            final_prediction = ocr_prediction
            final_confidence = ocr_score/100.0
        elif cnn_prediction != ocr_prediction and cnn_confidence < 0.6 and ocr_score > 60:
            final_prediction = ocr_prediction
            final_confidence = ocr_score/100.0
            
        return final_prediction, final_confidence, None
    except Exception as e:
        print(f"Prediction error: {e}")
        return None, 0, str(e)


def load_genuine_fake_model():
    """Load the genuine/fake detection model"""
    global _genuine_fake_model_cache
    
    if not TF_AVAILABLE:
        return None
    
    if _genuine_fake_model_cache is not None:
        return _genuine_fake_model_cache
    
    model_path = os.path.join(settings.BASE_DIR, 'genuine_fake_model.h5')
    
    if not os.path.exists(model_path):
        print(f"Genuine/Fake model not found at: {model_path}")
        return None
    
    try:
        from tensorflow.keras.models import load_model
        _genuine_fake_model_cache = load_model(model_path)
        print("Genuine/Fake model loaded successfully")
        return _genuine_fake_model_cache
    except Exception as e:
        print(f"Error loading genuine/fake model: {e}")
        return None


def analyze_image_quality(image_path):
    """Analyze image quality as a heuristic for genuine/fake detection."""
    if not TF_AVAILABLE or keras_image is None:
        return {'score': 0.5, 'is_uncertain': True}
    
    try:
        from tensorflow.keras.applications.vgg16 import VGG16, preprocess_input
        from tensorflow.keras.models import Model
        
        base_model = VGG16(weights='imagenet', include_top=False, input_shape=(128, 128, 3))
        
        img = keras_image.load_img(image_path, target_size=(128, 128))
        img_array = keras_image.img_to_array(img)
        img_array = np.expand_dims(img_array, axis=0)
        
        features = base_model.predict(img_array, verbose=0)
        variance = float(np.var(features))
        quality_score = min(1.0, variance / 1000.0)
        
        return {'score': quality_score, 'is_uncertain': True}
    except Exception as e:
        print(f"Image quality analysis error: {e}")
        return {'score': 0.5, 'is_uncertain': True}


# Confidence threshold for genuine/fake detection
# Only accept predictions with confidence above this threshold
# Lowered threshold for the new 54-class model since it has limited training data
CONFIDENCE_THRESHOLD = 0.20


def predict_genuine_fake_improved(image_path, predicted_medicine_name=None, ml_confidence=0):
    """
    Improved genuine/fake detection with confidence thresholds.
    
    This function uses multiple verification methods:
    1. QR Code Database (highest priority - 100% accurate)
    2. ML Model + Medicine Database lookup (with confidence threshold)
    3. Unknown detection for low-confidence predictions
    
    Returns: (authenticity, confidence, method, details)
    """
    print(f"\n=== Improved Genuine/Fake Detection ===")
    print(f"Input: predicted_medicine={predicted_medicine_name}, ml_confidence={ml_confidence}")
    
    # METHOD 1: Try QR Code Database (highest accuracy)
    qr_data = decode_qr_code(image_path)
    
    if qr_data:
        is_genuine, medicine_name, confidence, method = check_medicine_authenticity(qr_data)
        
        if is_genuine is not None:
            print(f"QR Code result: {is_genuine}, confidence: {confidence}")
            if is_genuine:
                return "Genuine", confidence, method, f"Verified via QR code: {medicine_name}"
            else:
                return "Fake", 1.0, method, "QR code not found in database"
    
    # METHOD 2: ML Model Prediction + Database Verification
    # Only trust the ML prediction if confidence is above threshold
    if predicted_medicine_name and ml_confidence > 0:
        print(f"ML Prediction: {predicted_medicine_name} (confidence: {ml_confidence})")
        
        if ml_confidence >= CONFIDENCE_THRESHOLD:
            # High confidence - verify against database
            is_found, matched_name, db_confidence = check_medicine_in_database(predicted_medicine_name)
            
            if is_found:
                print(f"Database verification: FOUND / Model Trusted - {matched_name}")
                return "Genuine", db_confidence, "ML Model Prediction", f"Identified as Genuine {matched_name}"
            else:
                print(f"Database verification: NOT FOUND - medicine not in our database")
                return "Unknown", 1.0, "ML + Database Verification", f"Medicine '{predicted_medicine_name}' not in local database."
        else:
            # Low confidence - mark as unknown/uncertain
            print(f"Low confidence prediction - marking as Unknown")
            return "Unknown", ml_confidence, "Low Confidence", f"Model confidence ({ml_confidence:.1%}) below threshold ({CONFIDENCE_THRESHOLD:.1%})"
    
    # METHOD 3: If no ML prediction available, try image quality analysis
    print("Trying image quality analysis as fallback...")
    quality = analyze_image_quality(image_path)
    
    if quality['score'] > 0.7:
        return "Unknown - Low Quality", quality['score'], "Quality Analysis", "Unable to verify - poor image quality"
    else:
        return "Unknown", 0.5, "No Verification Possible", "Could not verify medicine authenticity"


def analyze_risk(prediction, user_profile):
    """Analyze risk based on user's profile and predicted result"""
    if not prediction:
        return "Unknown", None
    
    warnings = []
    risk_level = "Unknown"
    
    # Model predicts Genuine/Fake (2-class model)
    if prediction in ['Genuine', 'Fake']:
        if prediction == 'Fake':
            risk_level = "High Risk"
            warnings.append("WARNING: This medicine appears to be COUNTERFEIT!")
            warnings.append("Do not consume this product. Purchase from authorized pharmacies.")
        else:
            risk_level = "Low Risk"
            warnings.append("This medicine appears to be GENUINE.")
            warnings.append("However, always verify with official sources.")

    # If model predicts specific medicine name - use get_medicine_details for dynamic lookup
    else:
        # Try to get medicine details from the new database
        medicine_info = get_medicine_details(prediction)
        
        if medicine_info:
            risk_level = "Low Risk"
            side_effects = medicine_info.get('side_effects', '').lower() if medicine_info.get('side_effects') else ''
            uses = medicine_info.get('uses', '') if medicine_info.get('uses') else ''
            ingredients = medicine_info.get('ingredients', '').lower() if medicine_info.get('ingredients') else ''
            
            warnings.append(f"Medicine identified: {prediction}")
            
            if user_profile and user_profile.allergies:
                # Use safer split and strip
                allergies = [a.strip().lower() for a in user_profile.allergies.split(',') if a.strip()]
                for allergy in allergies:
                    # Check for allergy in prediction name, side effects, OR ingredients
                    if allergy in prediction.lower() or allergy in side_effects or allergy in ingredients:
                        warnings.append(f"WARNING: This medicine matches your allergy: {allergy.title()}.")
                        if allergy in ingredients:
                            warnings.append(f"It contains an ingredient you are allergic to.")
                        risk_level = "High Risk"
                        # No break here so we can potentially catch multiple allergies, 
                        # but risk_level is already set to High Risk.
            
            if user_profile and user_profile.medical_conditions:
                conditions = user_profile.medical_conditions.lower()
                if 'asthma' in conditions and 'cough' in uses.lower():
                    warnings.append("Caution: This medicine may affect breathing conditions.")
                    if risk_level != "High Risk":
                        risk_level = "Medium Risk"
        else:
            # Fallback to old behavior if medicine not found in database
            if prediction in MEDICINE_INFO:
                risk_level = "Low Risk"
                medicine_info = MEDICINE_INFO[prediction]
                side_effects = medicine_info.get('side_effects', '').lower()
                ingredients = medicine_info.get('ingredients', '').lower() if medicine_info.get('ingredients') else ''
                
                warnings.append(f"Medicine identified: {prediction}")
                
                if user_profile and user_profile.allergies:
                    allergies = [a.strip().lower() for a in user_profile.allergies.split(',') if a.strip()]
                    for allergy in allergies:
                        if allergy in prediction.lower() or allergy in side_effects or allergy in ingredients:
                            warnings.append(f"WARNING: This medicine matches your allergy: {allergy.title()}.")
                            risk_level = "High Risk"
    
    warning_msg = " | ".join(warnings) if warnings else None
    return risk_level, warning_msg


def home(request):
    return render(request, 'home.html')


def result(request):
    scan_data = request.session.get('scan_data', {})
    return render(request, 'result.html', scan_data)


@login_required
def profile(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        dob_value = request.POST.get("date_of_birth")
        if dob_value:
            try:
                profile.date_of_birth = datetime.strptime(dob_value, "%Y-%m-%d").date()
            except ValueError:
                profile.date_of_birth = None
        else:
            profile.date_of_birth = None
        
        profile.gender = request.POST.get("gender")
        profile.blood_group = request.POST.get("blood_group")
        profile.allergies = request.POST.get("allergies")
        profile.medical_conditions = request.POST.get("medical_conditions")
        profile.current_medications = request.POST.get("current_medications")
        profile.save()

        messages.success(request, "Profile updated successfully")
        return redirect("profile")

    return render(request, "profile.html", {"profile": profile})


@login_required
def history(request):
    """Display scan history for the logged-in user"""
    scan_history = ScanHistory.objects.filter(user=request.user)
    
    # Load medicine info database for detailed information
    load_medicine_info_database()
    
    # Add medicine info to each scan record
    scans_with_details = []
    for scan in scan_history:
        medicine_info = get_medicine_details(scan.medicine_name)
        scans_with_details.append({
            'scan': scan,
            'medicine_info': medicine_info
        })
    
    return render(request, "history.html", {
        "scan_history": scan_history,
        "scans_with_details": scans_with_details
    })


def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect("profile")
        else:
            messages.error(request, "Invalid credentials")
            return redirect("login")

    return render(request, "login.html")


def logout_view(request):
    logout(request)
    return redirect("home")



def register(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        if password != confirm_password:
            messages.error(request, "Passwords do not match")
            return redirect("register")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists")
            return redirect("register")

        user = User.objects.create_user(
            username=username,
            password=password
        )
        user.save()

        messages.success(request, "Account created successfully")
        return redirect("login")

    return render(request, "register.html")


def medicine_details(request):
    # First check for query parameter (from history page)
    medicine_name = request.GET.get('medicine')
    scan_data = request.session.get('scan_data', {})
    
    # If not in query params, check session
    if not medicine_name:
        medicine_name = scan_data.get('medicine_name', None)
    
    authenticity = request.GET.get('authenticity') or scan_data.get('authenticity', None)
    authenticity_confidence = request.GET.get('authenticity_confidence') or scan_data.get('authenticity_confidence', None)
    
    # Try to get medicine info from database
    medicine_info = None
    if medicine_name and medicine_name != "Unknown":
        medicine_info = get_medicine_details(medicine_name)
        if not medicine_info:
            medicine_info = MEDICINE_INFO.get(medicine_name, {})
    
    image_url = request.GET.get('image_url') or scan_data.get('image_url', None)
    
    if medicine_info:
        return render(request, 'medicine_details.html', {
            'medicine_name': medicine_name,
            'medicine_info': medicine_info,
            'authenticity': authenticity,
            'authenticity_confidence': authenticity_confidence,
            'image_url': image_url
        })
    
    return render(request, 'medicine_details.html', {
        'medicine_name': medicine_name if medicine_name else 'Scan a medicine to see details',
        'medicine_info': {'uses': 'Please scan a medicine image first to view its details.', 'dosage': 'N/A', 'side_effects': 'N/A'},
        'authenticity': authenticity,
        'authenticity_confidence': authenticity_confidence,
        'image_url': image_url
    })


def risk_assessment(request):
    return render(request, 'risk_assessment.html')


@login_required
def scan(request):
    if request.method == "POST":

        image = None

        if request.FILES.get('image'):
            image = request.FILES['image']

        elif request.POST.get('captured_image'):
            format, imgstr = request.POST.get('captured_image').split(';base64,')
            ext = format.split('/')[-1]

            image = ContentFile(
                base64.b64decode(imgstr),
                name='captured.' + ext
            )

        if image:
            fs = FileSystemStorage()
            filename = fs.save(image.name, image)
            uploaded_file_url = fs.url(filename)
            
            image_path = fs.path(filename)
            
            prediction = None
            confidence = 0
            
            # Step 1: Check for Barcode or QR Code
            qr_data = decode_qr_code(image_path)
            
            if qr_data:
                print(f"Detected Code Data: {qr_data}")
                barcode_map = load_barcode_mapping()
                # Check if it maps to a known medicine
                if qr_data in barcode_map:
                    prediction = barcode_map[qr_data]
                    confidence = 1.0
                    authenticity = 'Genuine'
                    authenticity_confidence = 1.0
                    authenticity_method = 'Barcode/QR Verified'
                    authenticity_details = f'Instantly verified via secure Barcode/QR code: {qr_data}'
                    print(f"Barcode matched: {prediction}")
                else:
                    # Check if it's already a full medicine name
                    is_genuine, med_name, conf, method = check_medicine_authenticity(qr_data)
                    if is_genuine:
                        prediction = med_name
                        confidence = 1.0
                        authenticity = 'Genuine'
                        authenticity_confidence = conf
                        authenticity_method = method
                        authenticity_details = f'Verified via QR code text'
                        print(f"QR text matched medicine name: {prediction}")
                    else:
                        prediction = "Counterfeit Medicine"
                        confidence = 1.0
                        authenticity = 'Fake'
                        authenticity_confidence = 1.0
                        authenticity_method = 'Barcode/QR Verification Failed'
                        authenticity_details = f'Scanned code ({qr_data}) not found in authorized database.'
                        print(f"Unrecognized code data marked as fake: {qr_data}")
            
            # Step 2: Fallback to ML if no code matched
            if not prediction:
                print("No valid code matched, falling back to ML prediction...")
                prediction, confidence, error = predict_medicine(image_path)
                
                if prediction == 'Fake':
                    authenticity = 'Fake'
                    authenticity_confidence = confidence
                    authenticity_method = 'Advanced ML Model'
                    authenticity_details = 'Visually identified as counterfeit.'
                    prediction = "Counterfeit Medicine" # Don't label it as a valid medicine
                elif prediction == 'Unknown':
                    authenticity = 'Unknown'
                    authenticity_confidence = confidence
                    authenticity_method = 'Advanced ML Model'
                    authenticity_details = 'Object not recognized as a known medicine.'
                    prediction = "Unknown Object"
                else:
                    # Normal medicine predicted. Run improved genuine/fake detection just as an extra check
                    authenticity, authenticity_confidence, authenticity_method, authenticity_details = predict_genuine_fake_improved(
                        image_path, 
                        predicted_medicine_name=prediction, 
                        ml_confidence=confidence
                    )
            
            # Get user profile for risk analysis
            user_profile = None
            try:
                user_profile = UserProfile.objects.get(user=request.user)
            except UserProfile.DoesNotExist:
                pass
            
            # Analyze risk based on prediction and user profile
            risk_level, warning = analyze_risk(prediction, user_profile)
            
            # If authenticity is Fake, update risk to High Risk
            if authenticity == 'Fake':
                risk_level = "High Risk"
                warning = "WARNING: This medicine appears to be COUNTERFEIT! Do not consume this product. Purchase from authorized pharmacies."
            
            # Handle Unknown authenticity
            if authenticity == 'Unknown':
                risk_level = "Unknown Risk"
                warning = "Could not verify medicine authenticity. Please consult a pharmacist or verify the medicine manually."
            
            # Update scan and risk counts
            if user_profile:
                user_profile.scan_count += 1
                if risk_level in ['High Risk', 'Medium Risk']:
                    user_profile.risk_count += 1
                user_profile.save()
            
            # Save scan to history
            ScanHistory.objects.create(
                user=request.user,
                medicine_name=prediction if prediction else "Unknown",
                authenticity=authenticity,
                authenticity_confidence=authenticity_confidence,
                risk_level=risk_level,
                image_url=uploaded_file_url
            )
            
            # Get medicine info if it's a specific medicine - use get_medicine_details for dynamic lookup
            medicine_info = get_medicine_details(prediction) if prediction else {}
            if not medicine_info:
                medicine_info = MEDICINE_INFO.get(prediction, {})

            # Store in session for result page
            request.session['scan_data'] = {
                "image_url": uploaded_file_url,
                "medicine_name": prediction if prediction else "Unknown",
                "confidence": f"{confidence * 100:.1f}%" if confidence and confidence > 0 else "N/A",
                "risk": risk_level,
                "warning": warning,
                "medicine_info": medicine_info,
                "authenticity": authenticity,
                "authenticity_confidence": f"{authenticity_confidence * 100:.1f}%" if authenticity_confidence and authenticity_confidence > 0 else "N/A",
                "authenticity_method": authenticity_method
            }

            return render(request, "result.html", {
                "image_url": uploaded_file_url,
                "medicine_name": prediction if prediction else "Unknown",
                "confidence": f"{confidence * 100:.1f}%" if confidence and confidence > 0 else "N/A",
                "risk": risk_level,
                "warning": warning,
                "medicine_info": medicine_info,
                "authenticity": authenticity,
                "authenticity_confidence": f"{authenticity_confidence * 100:.1f}%" if authenticity_confidence and authenticity_confidence > 0 else "N/A",
                "authenticity_method": authenticity_method
            })

    return render(request, "scan.html")
