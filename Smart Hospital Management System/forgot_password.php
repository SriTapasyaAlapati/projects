<?php
require_once 'config.php';
session_start();

$step = 1;
$message = "";
$type = "";

if ($_SERVER["REQUEST_METHOD"] == "POST") {
    
    if (isset($_POST['send_otp'])) {
        $patient_id = $_POST['patient_id'];
        $phone = $_POST['phone'];
        
        $conn = getConnection();
        $stmt = $conn->prepare("SELECT patient_id, name, emergency_contact_phone FROM patients WHERE patient_id = ? AND emergency_contact_phone = ?");
        $stmt->bind_param("is", $patient_id, $phone);
        $stmt->execute();
        $result = $stmt->get_result();
        
        if ($result->num_rows > 0) {
            $patient = $result->fetch_assoc();
            
            $otp = rand(100000, 999999);
            $_SESSION['reset_patient_id'] = $patient_id;
            $_SESSION['reset_otp'] = $otp;
            $_SESSION['reset_otp_time'] = time();
            
            $message = "Your OTP is: " . $otp;
            $type = "success";
            $step = 2;
        } else {
            $message = "Patient ID and phone number do not match our records.";
            $type = "error";
        }
        $conn->close();
        
    } elseif (isset($_POST['verify_otp'])) {
        $entered_otp = $_POST['otp'];
        
        if (isset($_SESSION['reset_otp']) && isset($_SESSION['reset_otp_time'])) {
            $time_elapsed = time() - $_SESSION['reset_otp_time'];
            
            if ($time_elapsed > 600) {
                $message = "OTP has expired. Please request a new one.";
                $type = "error";
                $step = 1;
                unset($_SESSION['reset_otp']);
                unset($_SESSION['reset_otp_time']);
            } elseif ($entered_otp == $_SESSION['reset_otp']) {
                $step = 3;
                $message = "OTP verified. Please enter your new password.";
                $type = "success";
            } else {
                $message = "Invalid OTP. Please try again.";
                $type = "error";
                $step = 2;
            }
        } else {
            $message = "Session expired. Please request OTP again.";
            $type = "error";
            $step = 1;
        }
        
    } elseif (isset($_POST['reset_password'])) {
        $new_password = $_POST['new_password'];
        $confirm_password = $_POST['confirm_password'];
        
        if ($new_password !== $confirm_password) {
            $message = "Passwords do not match.";
            $type = "error";
            $step = 3;
        } elseif (strlen($new_password) < 6) {
            $message = "Password must be at least 6 characters.";
            $type = "error";
            $step = 3;
        } else {
            $conn = getConnection();
            $hashed_password = password_hash($new_password, PASSWORD_DEFAULT);
            $stmt = $conn->prepare("UPDATE patients SET password = ? WHERE patient_id = ?");
            $stmt->bind_param("si", $hashed_password, $_SESSION['reset_patient_id']);
            
            if ($stmt->execute()) {
                $message = "Password reset successfully! Please login with your new password.";
                $type = "success";
                $step = 4;
                unset($_SESSION['reset_patient_id']);
                unset($_SESSION['reset_otp']);
                unset($_SESSION['reset_otp_time']);
            } else {
                $message = "Error resetting password. Please try again.";
                $type = "error";
                $step = 3;
            }
            $conn->close();
        }
    }
}
?>

<!DOCTYPE html>
<html>
<head>
    <title>Forgot Password</title>
    <link rel="stylesheet" href="style.css">
    <link rel="stylesheet" href="login.css">
</head>
<body>

<form method="POST">
    <h2>Reset Password</h2>

    <?php if ($message): ?>
        <div class="<?php echo $type; ?>-msg"><?php echo $message; ?></div>
    <?php endif; ?>

    <?php if ($step == 1): ?>
        <label>Patient ID:</label>
        <input type="number" name="patient_id" required>
        
        <label>Registered Phone Number:</label>
        <input type="text" name="phone" required pattern="[0-9]{10}">
        
        <button type="submit" name="send_otp">Send OTP</button>
        
    <?php elseif ($step == 2): ?>
        <label>Enter OTP:</label>
        <input type="number" name="otp" required>
        
        <button type="submit" name="verify_otp">Verify OTP</button>
        
    <?php elseif ($step == 3): ?>
        <label>New Password:</label>
        <input type="password" name="new_password" required>
        
        <label>Confirm Password:</label>
        <input type="password" name="confirm_password" required>
        
        <button type="submit" name="reset_password">Reset Password</button>
        
    <?php elseif ($step == 4): ?>
        <p><a href="login.php">Click here to login</a></p>
    <?php endif; ?>
    
    <div style="text-align: center; margin-top: 15px;">
        <a href="login.php" style="color: #2a7de1;">Back to Login</a>
    </div>
</form>

</body>
</html>