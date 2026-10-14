<?php
require_once 'config.php';
session_start();
if (!isset($_SESSION['patient_id'])) {
    header("Location: login.php");
    exit();
}

$patient_id = $_SESSION['patient_id'];
$patient_name = $_SESSION['patient_name'];

$conn = getConnection();
$stmt = $conn->prepare("SELECT * FROM patients WHERE patient_id = ?");
$stmt->bind_param("i", $patient_id);
$stmt->execute();
$patient = $stmt->get_result()->fetch_assoc();
$conn->close();
?>

<!DOCTYPE html>
<html>
<head>
    <title>Patient Dashboard</title>
    <link rel="stylesheet" href="style.css">
    <style>
        .dashboard-container {
            max-width: 1000px;
            margin: 50px auto;
            background: rgba(255,255,255,0.95);
            border-radius: 10px;
            padding: 30px;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid #2a7de1;
            padding-bottom: 15px;
            margin-bottom: 30px;
        }
        .logout-btn {
            background: #dc3545;
            padding: 10px 20px;
            text-decoration: none;
            color: white;
            border-radius: 5px;
        }
        .info-card {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        .nav-buttons {
            display: flex;
            gap: 15px;
            margin-top: 20px;
            flex-wrap: wrap;
        }
        .nav-btn {
            background: #2a7de1;
            padding: 12px 25px;
            text-decoration: none;
            color: white;
            border-radius: 5px;
            display: inline-block;
        }
        .nav-btn:hover {
            background: #1f5fbf;
        }
    </style>
</head>
<body>

<div class="dashboard-container">
    <div class="header">
        <h1>Welcome, <?php echo $patient['name']; ?>!</h1>
        <a href="logout.php" class="logout-btn">Logout</a>
    </div>
    
    <div class="info-card">
        <h3>Your Information</h3>
        <p><strong>Patient ID:</strong> <?php echo $patient['patient_id']; ?></p>
        <p><strong>Name:</strong> <?php echo $patient['name']; ?></p>
        <p><strong>Blood Group:</strong> <?php echo $patient['blood_group']; ?></p>
        <p><strong>Phone:</strong> <?php echo $patient['emergency_contact_phone']; ?></p>
    </div>
    
    <div class="nav-buttons">
        <a href="chatbot.php" class="nav-btn">🤖 Symptom Checker</a>
        <a href="book_appointment.php" class="nav-btn">Book Appointment</a>
        <a href="my_appointments.php" class="nav-btn">My Appointments</a>
        <a href="medical_records.php" class="nav-btn">Medical Records</a>
    </div>
</div>

</body>
</html>