<?php
require_once 'config.php';
session_start();

if (!isset($_SESSION['doctor_id'])) {
    header("Location: doctor.php");
    exit();
}

$doctor_id = $_SESSION['doctor_id'];
$message = "";
$type = "";

$conn = getConnection();

// Get current availability
$doctor = $conn->prepare("SELECT * FROM doctors WHERE doctor_id = ?");
$doctor->bind_param("i", $doctor_id);
$doctor->execute();
$current = $doctor->get_result()->fetch_assoc();

if ($_SERVER["REQUEST_METHOD"] == "POST") {
    $is_available = isset($_POST['is_available']) ? 1 : 0;
    $consultation_fee = $_POST['consultation_fee'];
    $available_days = implode(',', $_POST['available_days'] ?? []);
    $available_from = $_POST['available_from'];
    $available_to = $_POST['available_to'];
    $max_appointments = $_POST['max_appointments_per_day'];
    
    $update = $conn->prepare("
        UPDATE doctors 
        SET is_available = ?, consultation_fee = ?, available_days = ?, 
            available_from = ?, available_to = ?, max_appointments_per_day = ?
        WHERE doctor_id = ?
    ");
    $update->bind_param("idsssii", $is_available, $consultation_fee, $available_days, $available_from, $available_to, $max_appointments, $doctor_id);
    
    if ($update->execute()) {
        $message = "Availability updated successfully!";
        $type = "success";
        // Refresh data
        $doctor->execute();
        $current = $doctor->get_result()->fetch_assoc();
    } else {
        $message = "Error updating availability: " . $update->error;
        $type = "error";
    }
    $update->close();
}

$conn->close();
$days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
$current_days = explode(',', $current['available_days'] ?? '');
?>

<!DOCTYPE html>
<html>
<head>
    <title>Update Availability - Doctor Dashboard</title>
    <link rel="stylesheet" href="style.css">
    <style>
        .container {
            max-width: 600px;
            margin: 50px auto;
            background: rgba(255,255,255,0.95);
            border-radius: 10px;
            padding: 30px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: bold;
            color: #333;
        }
        input, select {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
        }
        .checkbox-group {
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
        }
        .checkbox-group label {
            display: flex;
            align-items: center;
            gap: 5px;
            font-weight: normal;
        }
        .checkbox-group input {
            width: auto;
        }
        .update-btn {
            background: #28a745;
            color: white;
            border: none;
            padding: 12px 25px;
            border-radius: 5px;
            cursor: pointer;
            width: 100%;
            font-size: 16px;
        }
        .update-btn:hover {
            background: #1e7e34;
        }
        .back-btn {
            display: inline-block;
            margin-top: 20px;
            padding: 10px 20px;
            background: #6c757d;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            text-align: center;
        }
        .success-msg {
            background: #d4edda;
            color: #155724;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 15px;
        }
        .error-msg {
            background: #f8d7da;
            color: #721c24;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 15px;
        }
        h2 {
            color: #1e3a5f;
        }
    </style>
</head>
<body>
<div class="container">
    <h2>🟢 Update Availability</h2>
    
    <?php if ($message): ?>
        <div class="<?php echo $type; ?>-msg"><?php echo $message; ?></div>
    <?php endif; ?>
    
    <form method="POST">
        <div class="form-group">
            <label>
                <input type="checkbox" name="is_available" value="1" <?php echo $current['is_available'] ? 'checked' : ''; ?>>
                I am available for consultations
            </label>
        </div>
        
        <div class="form-group">
            <label>Consultation Fee (₹)</label>
            <input type="number" name="consultation_fee" step="50" value="<?php echo $current['consultation_fee'] ?? 500; ?>" required>
        </div>
        
        <div class="form-group">
            <label>Available Days</label>
            <div class="checkbox-group">
                <?php foreach($days_of_week as $day): ?>
                    <label>
                        <input type="checkbox" name="available_days[]" value="<?php echo $day; ?>" 
                            <?php echo in_array($day, $current_days) ? 'checked' : ''; ?>>
                        <?php echo $day; ?>
                    </label>
                <?php endforeach; ?>
            </div>
        </div>
        
        <div class="form-group">
            <label>Available From (Time)</label>
            <input type="time" name="available_from" value="<?php echo $current['available_from'] ?? '09:00'; ?>" required>
        </div>
        
        <div class="form-group">
            <label>Available To (Time)</label>
            <input type="time" name="available_to" value="<?php echo $current['available_to'] ?? '17:00'; ?>" required>
        </div>
        
        <div class="form-group">
            <label>Max Appointments Per Day</label>
            <input type="number" name="max_appointments_per_day" min="1" max="50" value="<?php echo $current['max_appointments_per_day'] ?? 20; ?>" required>
        </div>
        
        <button type="submit" class="update-btn">Update Availability</button>
    </form>
    
    <a href="doctor_dashboard.php" class="back-btn">← Back to Dashboard</a>
</div>
</body>
</html>