<?php
require_once 'config.php';
session_start();

$error = "";

$conn = getConnection();

if ($_SERVER["REQUEST_METHOD"] == "POST") {
    
    $doctor_id = $_POST['doctor_id'];
    $password = $_POST['password'];
    
    // Validate positive Doctor ID
    if ($doctor_id <= 0) {
        $error = "Invalid Doctor ID. Doctor ID must be a positive number.";
    } elseif (!is_numeric($doctor_id)) {
        $error = "Doctor ID must be a number.";
    } else {
        // Prepare statement to fetch doctor details
        $sql = "SELECT doctor_id, specialization, password FROM doctors WHERE doctor_id = ?";
        $stmt = $conn->prepare($sql);
        $stmt->bind_param("i", $doctor_id);
        $stmt->execute();
        $stmt->store_result();
        
        if ($stmt->num_rows > 0) {
            $stmt->bind_result($db_doctor_id, $specialization, $hashed_password);
            $stmt->fetch();
            
            if (password_verify($password, $hashed_password)) {
                $_SESSION['doctor_id'] = $db_doctor_id;
                $_SESSION['doctor_specialization'] = $specialization;
                $_SESSION['login_time'] = time();
                
                header("Location: doctor_dashboard.php");
                exit();
            } else {
                $error = "Invalid password! Please try again.";
            }
        } else {
            $error = "Doctor ID not found! Please contact administrator.";
        }
        $stmt->close();
    }
}
$conn->close();
?>

<!DOCTYPE html>
<html>
<head>
    <title>Doctor Login - SCIS Hospital</title>
    <link rel="stylesheet" href="doctor.css">
    <link rel="stylesheet" href="style.css">
    <style>
        .info-box {
            background: #e3f2fd;
            border-left: 4px solid #2a7de1;
            padding: 10px;
            margin-bottom: 15px;
            font-size: 12px;
            color: #1565c0;
        }
        .help-link {
            display: block;
            text-align: center;
            margin-top: 15px;
            font-size: 12px;
            color: #666;
            text-decoration: none;
        }
        .help-link:hover {
            color: #2a7de1;
        }
        .error-msg {
            background: #ffebee;
            color: #c62828;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 15px;
            border-left: 4px solid #c62828;
        }
        .warning-text {
            font-size: 11px;
            color: #666;
            margin-top: -5px;
            margin-bottom: 10px;
        }
        input[type=number] {
            -moz-appearance: textfield;
        }
    </style>
</head>
<body>

<form method="POST">
    <h2>Doctor Login</h2>
    <?php if ($error): ?>
        <div class="error-msg"><?php echo $error; ?></div>
    <?php endif; ?>

    <label>Doctor ID :</label>
    <input type="number" name="doctor_id" placeholder="Enter your positive Doctor ID" required autofocus min="1" step="1">

    <label>Password:</label>
    <input type="password" name="password" placeholder="Enter your password" required>

    <button type="submit">Login to Dashboard</button>
    
    <a href="index.html" class="help-link">← Back to Home</a>
</form>

<script>
// Client-side validation for Doctor ID
document.querySelector('input[name="doctor_id"]').addEventListener('input', function() {
    var val = parseInt(this.value);
    if (val <= 0 || isNaN(val)) {
        this.setCustomValidity('Doctor ID must be a positive number (1, 2, 3, ...)');
        this.style.borderColor = '#dc3545';
    } else {
        this.setCustomValidity('');
        this.style.borderColor = '#28a745';
    }
});

document.querySelector('form').addEventListener('submit', function(e) {
    var doctorId = parseInt(document.querySelector('input[name="doctor_id"]').value);
    if (doctorId <= 0 || isNaN(doctorId)) {
        alert('Please enter a valid positive Doctor ID (1, 2, 3, ...)');
        e.preventDefault();
        return false;
    }
});
</script>

</body>
</html>