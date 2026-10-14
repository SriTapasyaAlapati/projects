<?php
require_once 'config.php';

session_start();

$message = "";
$type = "";

if ($_SERVER["REQUEST_METHOD"] == "POST") {
    
    $patient_id = $_POST['patient_id'];
    $password = $_POST['password'];
    
    $conn = getConnection();
    
    $sql = "SELECT patient_id, name, password FROM patients WHERE patient_id = ?";
    $stmt = $conn->prepare($sql);
    $stmt->bind_param("i", $patient_id);
    $stmt->execute();
    $result = $stmt->get_result();
    
    if ($result->num_rows > 0) {
        $user = $result->fetch_assoc();
        
        if (password_verify($password, $user['password'])) {
            $_SESSION['patient_id'] = $user['patient_id'];
            $_SESSION['patient_name'] = $user['name'];
            $_SESSION['login_time'] = time();
            
            header("Location: patient_dashboard.php");
            exit();
        } else {
            $message = "Invalid password!";
            $type = "error";
        }
    } else {
        $message = "User does not exist!";
        $type = "error";
    }
    
    $stmt->close();
    $conn->close();
}
?>

<!DOCTYPE html>
<html>
<head>
    <title>Patient Login</title>
    <link rel="stylesheet" href="style.css">
    <link rel="stylesheet" href="login.css">
</head>
<body>

<form method="POST">
    <h2>Patient Login</h2>

    <?php if ($message): ?>
        <div class="<?php echo $type; ?>-msg"><?php echo $message; ?></div>
    <?php endif; ?>

    <label>Patient ID:</label>
    <input type="number" name="patient_id" required autofocus min="1" step="1">

    <label>Password:</label>
    <input type="password" name="password" required>

    <button type="submit">Login</button>
    
    <div style="text-align: center; margin-top: 15px;">
        <a href="forgot_password.php" style="color: #2a7de1; text-decoration: none;">Forgot Password?</a>
    </div>
</form>

</body>
</html>