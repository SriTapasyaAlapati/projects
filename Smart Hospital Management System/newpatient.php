<?php
require_once 'config.php';

session_start();

$message = "";
$type = "";

// Basic validation functions
function validatePhone($phone) {
    return preg_match('/^[0-9]{10}$/', $phone);
}

function validateName($name) {
    return strlen($name) >= 2 && strlen($name) <= 100;
}

if ($_SERVER["REQUEST_METHOD"] == "POST") {
    
    $name = $_POST['name'];
    $dob = $_POST['date_of_birth'];
    $blood_group = $_POST['blood_group'];
    $phone = $_POST['emergency_contact_phone'];
    $emergency_contact_name = $_POST['emergency_contact_name'];
    $address = $_POST['address'];
    $city = $_POST['city'];
    $state = $_POST['state'];
    $postal_code = $_POST['postal_code'];
    
    // Medical history fields
    $medical_history = $_POST['medical_history'];
    $allergies = $_POST['allergies'];
    $current_medications = $_POST['current_medications'];
    
    $password = $_POST['password'];
    $confirm_password = $_POST['confirm_password'];
    
    $errors = array();
    
    if (empty($name)) {
        $errors[] = "Name is required";
    } elseif (!validateName($name)) {
        $errors[] = "Name must be between 2 and 100 characters";
    }
    
    if (empty($phone)) {
        $errors[] = "Phone number is required";
    } elseif (!validatePhone($phone)) {
        $errors[] = "Phone number must be exactly 10 digits";
    }
    
    if (empty($password)) {
        $errors[] = "Password is required";
    } elseif (strlen($password) < 6) {
        $errors[] = "Password must be at least 6 characters";
    }
    
    if ($password !== $confirm_password) {
        $errors[] = "Passwords do not match";
    }
    
    if (count($errors) > 0) {
        $message = implode("<br>", $errors);
        $type = "error";
    } else {
        $conn = getConnection();
        
        // Check if phone number already exists
        $checkStmt = $conn->prepare("SELECT patient_id FROM patients WHERE emergency_contact_phone = ?");
        $checkStmt->bind_param("s", $phone);
        $checkStmt->execute();
        $checkStmt->store_result();
        
        if ($checkStmt->num_rows > 0) {
            $message = "A patient with this phone number already exists.";
            $type = "error";
        } else {
            $hashed_password = password_hash($password, PASSWORD_DEFAULT);
            
            $sql = "INSERT INTO patients (name, date_of_birth, blood_group, emergency_contact_name, emergency_contact_phone, 
                    address, city, state, postal_code, medical_history, allergies, current_medications, password) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)";
            
            $stmt = $conn->prepare($sql);
            $stmt->bind_param("ssssssssssss", $name, $dob, $blood_group, $emergency_contact_name, $phone, 
                            $address, $city, $state, $postal_code, $medical_history, $allergies, $current_medications, $hashed_password);
            
            if ($stmt->execute()) {
                $new_id = $conn->insert_id;
                $message = "Registration Successful! Your Patient ID is: " . $new_id;
                $type = "success";
                // Clear form data on success
                $_POST = array();
            } else {
                $message = "Registration failed: " . $stmt->error;
                $type = "error";
            }
            $stmt->close();
        }
        $checkStmt->close();
        $conn->close();
    }
}
?>

<!DOCTYPE html>
<html>
<head>
    <title>Register Patient - SCIS Hospital</title>
    <link rel="stylesheet" href="style.css">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: Arial, Helvetica, sans-serif;
        }
        
        body {
            background-image: url("hospital.jpeg");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 30px;
        }
        
        .registration-container {
            max-width: 800px;
            margin: 0 auto;
            background: rgba(255,255,255,0.95);
            border-radius: 10px;
            padding: 30px;
            box-shadow: 0 0 20px rgba(0,0,0,0.2);
        }
        
        h2 {
            text-align: center;
            margin-bottom: 25px;
            color: #1e3a5f;
        }
        
        h3 {
            color: #1e3a5f;
            margin: 20px 0 15px 0;
            padding-bottom: 8px;
            border-bottom: 2px solid #2a7de1;
        }
        
        .form-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin-bottom: 15px;
        }
        
        .form-group {
            margin-bottom: 15px;
        }
        
        label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
            color: #333;
            font-size: 14px;
        }
        
        input, select, textarea {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 14px;
        }
        
        textarea {
            resize: vertical;
            min-height: 60px;
        }
        
        small {
            display: block;
            margin-top: 5px;
            color: #666;
            font-size: 12px;
        }
        
        button {
            width: 100%;
            padding: 14px;
            margin-top: 20px;
            font-size: 16px;
            font-weight: bold;
            border: none;
            border-radius: 6px;
            background: #2a7de1;
            color: white;
            cursor: pointer;
            transition: 0.3s;
        }
        
        button:hover {
            background: #1f5fbf;
            transform: scale(1.02);
        }
        
        .error-msg {
            background: #ffebee;
            color: #c62828;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 15px;
            border-left: 4px solid #c62828;
        }
        
        .success-msg {
            background: #e8f5e9;
            color: #2e7d32;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 15px;
            border-left: 4px solid #2e7d32;
        }
        
        .required:after {
            content: " *";
            color: red;
        }
        
        @media (max-width: 768px) {
            .form-row {
                grid-template-columns: 1fr;
            }
            .registration-container {
                padding: 20px;
            }
        }
    </style>
</head>
<body>

<div class="registration-container">
    <form method="POST">
        <h2>🏥 Patient Registration</h2>

        <?php if ($message): ?>
            <div class="<?php echo $type; ?>-msg"><?php echo $message; ?></div>
        <?php endif; ?>

        <h3>📋 Personal Information</h3>
        
        <div class="form-row">
            <div class="form-group">
                <label class="required">Full Name</label>
                <input type="text" name="name" required value="<?php echo isset($_POST['name']) ? htmlspecialchars($_POST['name']) : ''; ?>">
            </div>
            
            <div class="form-group">
                <label>Date of Birth</label>
                <input type="date" name="date_of_birth" value="<?php echo isset($_POST['date_of_birth']) ? $_POST['date_of_birth'] : ''; ?>">
            </div>
        </div>

        <div class="form-row">
            <div class="form-group">
                <label class="required">Blood Group</label>
                <select name="blood_group" required>
                    <option value="">Select Blood Group</option>
                    <option value="A+" <?php echo (isset($_POST['blood_group']) && $_POST['blood_group'] == 'A+') ? 'selected' : ''; ?>>A+</option>
                    <option value="A-" <?php echo (isset($_POST['blood_group']) && $_POST['blood_group'] == 'A-') ? 'selected' : ''; ?>>A-</option>
                    <option value="B+" <?php echo (isset($_POST['blood_group']) && $_POST['blood_group'] == 'B+') ? 'selected' : ''; ?>>B+</option>
                    <option value="B-" <?php echo (isset($_POST['blood_group']) && $_POST['blood_group'] == 'B-') ? 'selected' : ''; ?>>B-</option>
                    <option value="O+" <?php echo (isset($_POST['blood_group']) && $_POST['blood_group'] == 'O+') ? 'selected' : ''; ?>>O+</option>
                    <option value="O-" <?php echo (isset($_POST['blood_group']) && $_POST['blood_group'] == 'O-') ? 'selected' : ''; ?>>O-</option>
                    <option value="AB+" <?php echo (isset($_POST['blood_group']) && $_POST['blood_group'] == 'AB+') ? 'selected' : ''; ?>>AB+</option>
                    <option value="AB-" <?php echo (isset($_POST['blood_group']) && $_POST['blood_group'] == 'AB-') ? 'selected' : ''; ?>>AB-</option>
                </select>
            </div>
            
            <div class="form-group">
                <label class="required">Emergency Contact Phone</label>
                <input type="tel" name="emergency_contact_phone" required pattern="[0-9]{10}" 
                       title="10-digit mobile number" value="<?php echo isset($_POST['emergency_contact_phone']) ? $_POST['emergency_contact_phone'] : ''; ?>">
                <small>10-digit mobile number</small>
            </div>
        </div>

        <div class="form-row">
            <div class="form-group">
                <label>Emergency Contact Name</label>
                <input type="text" name="emergency_contact_name" value="<?php echo isset($_POST['emergency_contact_name']) ? htmlspecialchars($_POST['emergency_contact_name']) : ''; ?>">
                <small>Name of person to contact in emergency</small>
            </div>
        </div>

        <h3>📍 Address Information</h3>
        
        <div class="form-group">
            <label>Address</label>
            <textarea name="address" rows="2" placeholder="Street address, apartment, etc."><?php echo isset($_POST['address']) ? htmlspecialchars($_POST['address']) : ''; ?></textarea>
        </div>

        <div class="form-row">
            <div class="form-group">
                <label>City</label>
                <input type="text" name="city" value="<?php echo isset($_POST['city']) ? htmlspecialchars($_POST['city']) : ''; ?>">
            </div>
            
            <div class="form-group">
                <label>State</label>
                <input type="text" name="state" value="<?php echo isset($_POST['state']) ? htmlspecialchars($_POST['state']) : ''; ?>">
            </div>
            
            <div class="form-group">
                <label>Postal Code</label>
                <input type="text" name="postal_code" value="<?php echo isset($_POST['postal_code']) ? htmlspecialchars($_POST['postal_code']) : ''; ?>">
            </div>
        </div>

        <h3>🏥 Medical History</h3>
        
        <div class="form-group">
            <label>Past Medical History</label>
            <textarea name="medical_history" rows="3" placeholder="List any past illnesses, surgeries, chronic conditions, etc."><?php echo isset($_POST['medical_history']) ? htmlspecialchars($_POST['medical_history']) : ''; ?></textarea>
            <small>e.g., Diabetes, Hypertension, Asthma, Previous surgeries, etc.</small>
        </div>

        <div class="form-group">
            <label>Allergies</label>
            <textarea name="allergies" rows="2" placeholder="List any known allergies (medications, food, etc.)"><?php echo isset($_POST['allergies']) ? htmlspecialchars($_POST['allergies']) : ''; ?></textarea>
            <small>e.g., Penicillin, Peanuts, Latex, etc.</small>
        </div>

        <div class="form-group">
            <label>Current Medications</label>
            <textarea name="current_medications" rows="2" placeholder="List any medications you are currently taking"><?php echo isset($_POST['current_medications']) ? htmlspecialchars($_POST['current_medications']) : ''; ?></textarea>
            <small>Include dosage and frequency if known</small>
        </div>

        <h3>🔐 Account Setup</h3>
        
        <div class="form-row">
            <div class="form-group">
                <label class="required">Password</label>
                <input type="password" name="password" required minlength="6">
                <small>Password must be at least 6 characters</small>
            </div>
            
            <div class="form-group">
                <label class="required">Confirm Password</label>
                <input type="password" name="confirm_password" required>
            </div>
        </div>

        <button type="submit">Register Patient</button>
    </form>
</div>

<script>
document.querySelector('form').addEventListener('submit', function(e) {
    var password = document.querySelector('input[name="password"]').value;
    var confirm = document.querySelector('input[name="confirm_password"]').value;
    
    if (password !== confirm) {
        alert('Passwords do not match!');
        e.preventDefault();
        return false;
    }
    
    if (password.length < 6) {
        alert('Password must be at least 6 characters long!');
        e.preventDefault();
        return false;
    }
    
    var phone = document.querySelector('input[name="emergency_contact_phone"]').value;
    if (!/^\d{10}$/.test(phone)) {
        alert('Phone number must be exactly 10 digits!');
        e.preventDefault();
        return false;
    }
});
</script>

</body>
</html>