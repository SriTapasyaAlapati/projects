<?php
require_once 'config.php';
session_start();

if (!isset($_SESSION['patient_id'])) {
    header("Location: login.php");
    exit();
}

$patient_id = $_SESSION['patient_id'];
$message = "";
$type = "";

// Time slots for appointments
$available_slots = ["09:00:00", "10:00:00", "11:00:00", "14:00:00", "15:00:00", "16:00:00"];

// Get selected doctor from URL (from chatbot)
$selected_doctor_id = isset($_GET['doctor_id']) ? intval($_GET['doctor_id']) : 0;

$conn = getConnection();

// Fetch all doctors (using your doctors table)
$doctors_result = $conn->query("SELECT doctor_id, specialization, is_available FROM doctors ORDER BY doctor_id");

// Fetch patient's upcoming appointments (using your schema)
$upcoming = $conn->prepare("
    SELECT a.appointment_id, a.appointment_date, a.appointment_time, 
           a.status, a.symptoms_description, 
           COALESCE(a.urgency_level, 'low') as urgency_level,
           d.doctor_id, d.specialization
    FROM appointments a 
    JOIN doctors d ON a.doctor_id = d.doctor_id 
    WHERE a.patient_id = ? AND a.appointment_date >= CURDATE() AND a.status IN ('scheduled', 'confirmed')
    ORDER BY a.appointment_date, a.appointment_time
");
$upcoming->bind_param("i", $patient_id);
$upcoming->execute();
$upcoming_appointments = $upcoming->get_result();

if ($_SERVER["REQUEST_METHOD"] == "POST" && isset($_POST['book'])) {
    $doctor_id = intval($_POST['doctor_id']);
    $appointment_date = $_POST['appointment_date'];
    $appointment_time = $_POST['appointment_time'];
    $symptoms_description = trim($_POST['symptoms_description']);
    $urgency_level = isset($_POST['urgency_level']) ? $_POST['urgency_level'] : 'low';
    
    $errors = [];
    
    // Validate date (cannot be in past)
    if (strtotime($appointment_date) < strtotime(date('Y-m-d'))) {
        $errors[] = "Appointment date cannot be in the past.";
    }
    
    // Check if slot is already booked (using your unique constraint)
    $check = $conn->prepare("
        SELECT appointment_id FROM appointments 
        WHERE doctor_id = ? AND appointment_date = ? AND appointment_time = ? 
        AND status IN ('scheduled', 'confirmed')
    ");
    $check->bind_param("iss", $doctor_id, $appointment_date, $appointment_time);
    $check->execute();
    $check_result = $check->get_result();
    
    if ($check_result->num_rows > 0) {
        $errors[] = "This time slot is already booked. Please choose another slot.";
    }
    
    if (empty($errors)) {
        // Using your appointments table column names
        $stmt = $conn->prepare("
            INSERT INTO appointments (
                patient_id, doctor_id, appointment_date, appointment_time, 
                symptoms_description, urgency_level, status
            ) VALUES (?, ?, ?, ?, ?, ?, 'scheduled')
        ");
        $stmt->bind_param("iissss", $patient_id, $doctor_id, $appointment_date, $appointment_time, $symptoms_description, $urgency_level);
        
        if ($stmt->execute()) {
            $appointment_id = $conn->insert_id;
            $message = "Appointment booked successfully! Appointment ID: " . $appointment_id;
            $type = "success";
            // Refresh upcoming appointments
            $upcoming->execute();
            $upcoming_appointments = $upcoming->get_result();
        } else {
            $message = "Error booking appointment: " . $stmt->error;
            $type = "error";
        }
        $stmt->close();
    } else {
        $message = implode("<br>", $errors);
        $type = "error";
    }
    $check->close();
}

$conn->close();
?>

<!DOCTYPE html>
<html>
<head>
    <title>Book Appointment - SCIS Hospital</title>
    <link rel="stylesheet" href="style.css">
    <style>
        .appointment-container {
            max-width: 900px;
            margin: 30px auto;
            background: rgba(255,255,255,0.95);
            border-radius: 10px;
            padding: 30px;
            box-shadow: 0 0 15px rgba(0,0,0,0.1);
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
            color: #333;
        }
        select, input[type="date"], textarea {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 14px;
        }
        .book-btn {
            background: #28a745;
            color: white;
            border: none;
            padding: 12px 25px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
            width: 100%;
        }
        .book-btn:hover {
            background: #1e7e34;
        }
        .appointment-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        .appointment-table th, .appointment-table td {
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        .appointment-table th {
            background: #2a7de1;
            color: white;
        }
        .appointment-table tr:hover {
            background: #f5f5f5;
        }
        .status-scheduled, .status-confirmed {
            background: #ffc107;
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 12px;
            display: inline-block;
        }
        h2, h3 {
            color: #1e3a5f;
        }
        .cancel-btn {
            background: #dc3545;
            color: white;
            border: none;
            padding: 5px 10px;
            border-radius: 3px;
            cursor: pointer;
            font-size: 12px;
        }
        .cancel-btn:hover {
            background: #c82333;
        }
        hr {
            margin: 30px 0;
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
        .urgency-select {
            background: #fff3e0;
        }
        .urgency-badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
            color: white;
        }
        .urgency-low { background: #28a745; }
        .urgency-medium { background: #ffc107; color: #333; }
        .urgency-high { background: #ff9800; }
        .urgency-critical { background: #dc3545; }
        .back-link {
            display: inline-block;
            margin-top: 20px;
            color: #2a7de1;
            text-decoration: none;
        }
        .back-link:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
<div class="appointment-container">
    <h2>📅 Book a New Appointment</h2>
    
    <?php if ($message): ?>
        <div class="<?php echo $type; ?>-msg"><?php echo $message; ?></div>
    <?php endif; ?>
    
    <form method="POST">
        <div class="form-group">
            <label>Select Doctor *</label>
            <select name="doctor_id" required>
                <option value="">-- Select Doctor --</option>
                <?php 
                if ($doctors_result && $doctors_result->num_rows > 0):
                    while($doc = $doctors_result->fetch_assoc()): 
                ?>
                    <option value="<?php echo $doc['doctor_id']; ?>" 
                        <?php echo ($selected_doctor_id == $doc['doctor_id']) ? 'selected' : ''; ?>
                        <?php echo ($doc['is_available'] == 0) ? 'disabled' : ''; ?>>
                        Doctor ID: <?php echo $doc['doctor_id']; ?> - <?php echo htmlspecialchars($doc['specialization']); ?>
                        <?php echo ($doc['is_available'] == 0) ? ' (Currently Unavailable)' : ''; ?>
                    </option>
                <?php 
                    endwhile;
                else:
                ?>
                    <option value="" disabled>No doctors available</option>
                <?php endif; ?>
            </select>
        </div>
        
        <div class="form-group">
            <label>Appointment Date *</label>
            <input type="date" name="appointment_date" required min="<?php echo date('Y-m-d'); ?>">
        </div>
        
        <div class="form-group">
            <label>Time Slot *</label>
            <select name="appointment_time" required>
                <option value="">-- Select Time --</option>
                <?php foreach($available_slots as $slot): ?>
                    <option value="<?php echo $slot; ?>">
                        <?php echo date('g:i A', strtotime($slot)); ?>
                    </option>
                <?php endforeach; ?>
            </select>
        </div>
        
        <div class="form-group">
            <label>Urgency Level *</label>
            <select name="urgency_level" class="urgency-select" required>
                <option value="low">Low - Routine checkup</option>
                <option value="medium">Medium - Non-emergency but needs attention</option>
                <option value="high">High - Urgent, needs quick attention</option>
                <option value="critical">Critical - Emergency (Call 108 if severe)</option>
            </select>
        </div>
        
        <div class="form-group">
            <label>Symptoms / Reason for visit</label>
            <textarea name="symptoms_description" rows="3" placeholder="Describe your symptoms or reason for consultation"></textarea>
        </div>
        
        <button type="submit" name="book" class="book-btn">Confirm Appointment</button>
    </form>
    
    <hr>
    
    <h3>📋 Your Upcoming Appointments</h3>
    <?php if ($upcoming_appointments && $upcoming_appointments->num_rows > 0): ?>
        <table class="appointment-table">
            <thead>
                <tr>
                    <th>Date</th>
                    <th>Time</th>
                    <th>Doctor ID</th>
                    <th>Specialization</th>
                    <th>Urgency</th>
                    <th>Status</th>
                    <th>Action</th>
                </tr>
            </thead>
            <tbody>
                <?php while($apt = $upcoming_appointments->fetch_assoc()): 
                    $urgency = isset($apt['urgency_level']) ? $apt['urgency_level'] : 'low';
                ?>
                <tr>
                    <td><?php echo date('d M Y', strtotime($apt['appointment_date'])); ?></td>
                    <td><?php echo date('g:i A', strtotime($apt['appointment_time'])); ?></td>
                    <td><?php echo $apt['doctor_id']; ?></td>
                    <td><?php echo htmlspecialchars($apt['specialization']); ?></td>
                    <td>
                        <span class="urgency-badge urgency-<?php echo $urgency; ?>">
                            <?php echo ucfirst($urgency); ?>
                        </span>
                    </td>
                    <td><span class="status-scheduled"><?php echo $apt['status']; ?></span></td>
                    <td>
                        <form method="POST" action="cancel_appointment.php" style="display:inline;" onsubmit="return confirm('Are you sure you want to cancel this appointment?');">
                            <input type="hidden" name="appointment_id" value="<?php echo $apt['appointment_id']; ?>">
                            <button type="submit" name="cancel" class="cancel-btn">Cancel</button>
                        </form>
                    </td>
                </tr>
                <?php endwhile; ?>
            </tbody>
        </table>
    <?php else: ?>
        <p style="padding: 20px; background: #f8f9fa; text-align: center; border-radius: 8px;">
            No upcoming appointments. Use the form above to book an appointment.
        </p>
    <?php endif; ?>
    
    <div style="margin-top: 20px; text-align: center;">
        <a href="patient_dashboard.php" class="back-link">← Back to Dashboard</a>
    </div>
</div>

<script>
// Set minimum date for date picker
document.querySelector('input[name="appointment_date"]').min = new Date().toISOString().split('T')[0];
</script>
</body>
</html>