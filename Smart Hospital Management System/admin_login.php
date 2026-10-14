<?php
require_once 'config.php';
session_start();

// Create admin table if not exists
$conn = getConnection();
$conn->query("CREATE TABLE IF NOT EXISTS admins (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)");

// Check if default admin exists, if not create one
$check = $conn->query("SELECT id FROM admins WHERE username = 'admin'");
if ($check->num_rows == 0) {
    $default_password = password_hash('Admin123$', PASSWORD_DEFAULT);
    $conn->query("INSERT INTO admins (username, password) VALUES ('admin', '$default_password')");
}
$conn->close();

$message = "";
$type = "";

if ($_SERVER["REQUEST_METHOD"] == "POST") {
    
    $username = $_POST['username'];
    $password = $_POST['password'];
    
    $conn = getConnection();
    
    $stmt = $conn->prepare("SELECT id, username, password FROM admins WHERE username = ?");
    $stmt->bind_param("s", $username);
    $stmt->execute();
    $result = $stmt->get_result();
    
    if ($result->num_rows > 0) {
        $admin = $result->fetch_assoc();
        //Default Admin Credentials:
        // Username: admin
        //Password: Admin123$

        
        if (password_verify($password, $admin['password'])) {
            $_SESSION['admin'] = true;
            $_SESSION['admin_id'] = $admin['id'];
            $_SESSION['admin_username'] = $admin['username'];
            
            header("Location: admin_dashboard.php");
            exit();
        } else {
            $message = "Invalid credentials!";
            $type = "error";
        }
    } else {
        $message = "Invalid credentials!";
        $type = "error";
    }
    
    $stmt->close();
    $conn->close();
}
?>

<!DOCTYPE html>
<html>
<head>
    <title>Admin Login</title>
    <link rel="stylesheet" href="style.css">
    <link rel="stylesheet" href="login.css">
</head>
<body>

<form method="POST">
    <h2>Admin Login</h2>

    <?php if ($message): ?>
        <div class="<?php echo $type; ?>-msg"><?php echo $message; ?></div>
    <?php endif; ?>

    <label>Username:</label>
    <input type="text" name="username" required autofocus>

    <label>Password:</label>
    <input type="password" name="password" required>

    <button type="submit">Login</button>
</form>

</body>
</html>