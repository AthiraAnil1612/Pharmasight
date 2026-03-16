# 💊 PharmaSight: AI-Powered Medicine Verification & Safety

PharmaSight is a cutting-edge digital health platform designed to combat the global issue of counterfeit medications. Leveraging advanced Machine Learning (CNN), Optical Character Recognition (OCR), and secure code verification, PharmaSight empowers users to verify the authenticity of their medicines instantly and assess potential health risks based on their personal medical profiles.

---

## 🌟 Key Features

### 🔍 1. Multi-Layer Authenticity Verification
PharmaSight uses a robust three-tier verification system:
- **CNN-Based Identification**: A custom-trained Convolutional Neural Network (TensorFlow/Keras) identifies medicines based on visual packaging characteristics.
- **OCR Verification**: Cross-references text on labels with our authorized medicine database to detect inconsistencies.
- **Secure QR/Barcode Scanning**: Instantly validates secure codes against a tamper-proof digital registry.

### ⚠️ 2. Personalized Health Risk Assessment
Automatically flags potential dangers by matching identified medicine ingredients against:
- **User Allergies**: Instant warnings if a medicine contains known allergens.
- **Medical Conditions**: Alerts for contraindications (e.g., respiratory warnings for asthma patients).

### 📖 3. Comprehensive Medicine Encyclopedia
Access detailed information for thousands of medicines, including:
- Approved Uses & Indications
- Precise Dosage Instructions
- Potential Side Effects & Precautions

### 📋 4. User Health Management
- **Digital Health Profile**: Securely store allergies and conditions for automated risk checks.
- **Scan History**: Keep a historical record of all scanned medications for easy reference.

---

## 🛠️ Technology Stack

| Layer | Technology |
| :--- | :--- |
| **Backend** | Django (Python) |
| **AI / Machine Learning** | TensorFlow, Keras (CNN), MobileNetV2 |
| **Text Recognition** | EasyOCR, Rapidfuzz |
| **Data Recovery** | OpenCV, ZXing-cpp (QR/Barcode) |
| **Database** | SQLite3 (Application), JSON (Medicine Registry) |
| **Frontend** | HTML5, CSS3, JavaScript |

---

## 🚀 Getting Started

### Prerequisites
- Python 3.9+
- TensorFlow 2.x
- Django 4.x

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/pharmasight.git
   cd pharmasight
   ```

2. **Set up virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize Database**
   ```bash
   python manage.py migrate
   ```

5. **Run the Server**
   ```bash
   python manage.py runserver
   ```

---

## 📸 How It Works

1. **Upload or Capture**: Take a photo of the medicine packaging or scan the QR code.
2. **AI Analysis**: The system extracts features and text to identify the brand and batch.
3. **Verification**: PharmaSight checks the database to confirm if the batch is genuine.
4. **Safety Check**: The app cross-references the medicine's ingredients with your profile to ensure it's safe for you.

---

## 🛡️ Disclaimer
*PharmaSight is an AI-assisted tool meant for informational purposes. It is not a replacement for professional medical advice or official regulatory verification systems. Always consult with a licensed healthcare provider before starting new medications.*

---
