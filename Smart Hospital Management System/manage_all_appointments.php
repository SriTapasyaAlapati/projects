<?php
require_once 'config.php';
session_start();

if (!isset($_SESSION['doctor_id'])) {
    header("Location: doctor.php");
    exit();
}

$doctor_id = $_SESSION['doctor_id'];
$filter = isset($_GET['filter']) ? $_GET['filter'] : 'upcoming';
$message = "";
$type = "";

$conn = getConnection();

// Handle status update
if ($_SERVER["REQUEST_METHOD"] == "POST" && isset($_POST['update_status'])) {
    $appointment_id = intval($_POST['appointment_id']);
    $new_status = $_POST['new_status'];
    
    $update = $conn->prepare("UPDATE appointments SET status = ? WHERE appointment_id = ? AND doctor_id = ?");
    $update->bind_param("sii", $new_status, $appointment_id, $doctor_id);
    
    if ($update->execute()) {
        $message = "Appointment status updated successfully!";
        $type = "success";
    } else {
        $message = "Error updating status";
        $type = "error";
    }
    $update->close();
}

// Build query based on filter
$today = date('Y-m-d');
$query = "
    SELECT a.*, p.name as patient_name, p.blood_group, p.emergency_contact_phone
    FROM appointments a
    JOIN patients p ON a.patient_id = p.patient_id
    WHERE a.doctor_id = ?
";

if ($filter == 'upcoming') {
    $query .= " AND a.appointment_date >= ? AND a.status IN ('scheduled', 'confirmed') ORDER BY a.appointment_date, a.appointment_time";
    $stmt = $conn->prepare($query);
    $stmt->bind_param("is", $doctor_id, $today);
} elseif ($filter == 'today') {
    $query .= " AND a.appointment_date = ? ORDER BY a.appointment_time";
    $stmt = $conn->prepare($query);
    $stmt->bind_param("is", $doctor_id, $today);
} elseif ($filter == 'past') {
    $query .= " AND a.appointment_date < ? AND a.status IN ('completed', 'cancelled', 'no_show') ORDER BY a.appointment_date DESC";
    $stmt = $conn->prepare($query);
    $stmt->bind_param("is", $doctor_id, $today);
} else {
    $query .= " ORDER BY a.appointment_date DESC, a.appointment_time";
    $stmt = $conn->prepare($query);
    $stmt->bind_param("i", $doctor_id);
}

$stmt->execute();
$appointments = $stmt->get_result();
$conn->close();
?>

<!DOCTYPE html>
<html>
<head>
    <title>Manage Appointments - Doctor Dashboard</title>
    <link rel="stylesheet" href="style.css">
    <style>
        .container {
            max-width: 1300px;
            margin: 30px auto;
            background: rgba(255,255,255,0.95);
            border-radius: 10px;
            padding: 25px;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 25px;
            flex-wrap: wrap;
        }
        .filter-buttons {
            display: flex;
            gap: 10px;
        }
        .filter-btn {
            padding: 10px 20px;
            background: #e9ecef;
            color: #333;
            text-decoration: none;
            border-radius: 5px;
        }
        .filter-btn.active {
            background: #2a7de1;
            color: white;
        }
        .appointment-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        .appointment-table th, .appointment-table td {
            padding: 12px;
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
        .status-select {
            padding: 5px;
            border-radius: 4px;
            border: 1px solid #ddd;
        }
        .update-btn {
            background: #28a745;
            color: white;
            border: none;
            padding: 5px 10px;
            border-radius: 4px;
            cursor: pointer;
        }
        .view-btn {
            background: #17a2b8;
            color: white;
            padding: 5px 10px;
            text-decoration: none;
            border-radius: 4px;
        }
        .back-btn {
            display: inline-block;
            margin-top: 20px;
            padding: 10px 20px;
            background: #6c757d;
            color: white;
            text-decoration: none;
            border-radius: 5px;
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
    <div class="header">
        <h2>📅 Manage Appointments</h2>
        <div class="filter-buttons">
            <a href="?filter=upcoming" class="filter-btn <?php echo $filter == 'upcoming' ? 'active' : ''; ?>">Upcoming</a>
            <a href="?filter=today" class="filter-btn <?php echo $filter == 'today' ? 'active' : ''; ?>">Today</a>
            <a href="?filter=past" class="filter-btn <?php echo $filter == 'past' ? 'active' : ''; ?>">Past</a>
            <a href="?filter=all" class="filter-btn <?php echo $filter == 'all' ? 'active' : ''; ?>">All</a>
        </div>
    </div>
    
    <?php if ($message): ?>
        <div class="<?php echo $type; ?>-msg"><?php echo $message; ?></div>
    <?php endif; ?>
    
    <?php if ($appointments->num_rows > 0): ?>
        <table class="appointment-table">
            <thead>
                <tr>
                    <th>Date</th>
                    <th>Time</th>
                    <th>Patient</th>
                    <th>Contact</th>
                    <th>Symptoms</th>
                    <th>Status</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                <?php while($apt = $appointments->fetch_assoc()): ?>
                <tr>
                    <td><?php echo date('d M Y', strtotime($apt['appointment_date'])); ?></td>
                    <td><?php echo date('g:i A', strtotime($apt['appointment_time'])); ?></td>
                    <td><?php echo htmlspecialchars($apt['patient_name']); ?> (ID: <?php echo $apt['patient_id']; ?>)</td>
                    <td><?php echo $apt['emergency_contact_phone']; ?></td>
                    <td><?php echo substr(htmlspecialchars($apt['symptoms_description']), 0, 50); ?>...</td>
                    <td>
                        <form method="POST" style="display: flex; gap: 5px;">
                            <input type="hidden" name="appointment_id" value="<?php echo $apt['appointment_id']; ?>">
                            <select name="new_status" class="status-select">
                                <option value="scheduled" <?php echo $apt['status'] == 'scheduled' ? 'selected' : ''; ?>>Scheduled</option>
                                <option value="confirmed" <?php echo $apt['status'] == 'confirmed' ? 'selected' : ''; ?>>Confirmed</option>
                                <option value="completed" <?php echo $apt['status'] == 'completed' ? 'selected' : ''; ?>>Completed</option>
                                <option value="cancelled" <?php echo $apt['status'] == 'cancelled' ? 'selected' : ''; ?>>Cancelled</option>
                                <option value="no_show" <?php echo $apt['status'] == 'no_show' ? 'selected' : ''; ?>>No Show</option>
                            </select>
                            <button type="submit" name="update_status" class="update-btn">Update</button>
                        </form>
                    </td>
                    <td>
                        <a href="view_patient_details.php?id=<?php echo $apt['patient_id']; ?>&appointment_id=<?php echo $apt['appointment_id']; ?>" class="view-btn">View Details</a>
                    </td>
                </tr>
                <?php endwhile; ?>
            </tbody>
        </table>
    <?php else: ?>
        <p style="text-align: center; padding: 40px;">No appointments found.</p>
    <?php endif; ?>
    
    <a href="doctor_dashboard.php" class="back-btn">← Back to Dashboard</a>
</div>
</body>
</html>