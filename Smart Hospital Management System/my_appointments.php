<?php
require_once 'config.php';
session_start();

if (!isset($_SESSION['patient_id'])) {
    header("Location: login.php");
    exit();
}

$patient_id = $_SESSION['patient_id'];
$patient_name = $_SESSION['patient_name'];
$message = "";
$type = "";

$conn = getConnection();

// Handle appointment cancellation
if ($_SERVER["REQUEST_METHOD"] == "POST" && isset($_POST['cancel_appointment'])) {
    $appointment_id = intval($_POST['appointment_id']);
    
    $cancel_stmt = $conn->prepare("
        UPDATE appointments 
        SET status = 'cancelled', 
            cancelled_at = NOW(),
            cancellation_reason = 'Cancelled by patient'
        WHERE appointment_id = ? AND patient_id = ? AND status IN ('scheduled', 'confirmed')
    ");
    $cancel_stmt->bind_param("ii", $appointment_id, $patient_id);
    
    if ($cancel_stmt->execute() && $cancel_stmt->affected_rows > 0) {
        $message = "Appointment cancelled successfully!";
        $type = "success";
    } else {
        $message = "Unable to cancel appointment. It may have already been completed or cancelled.";
        $type = "error";
    }
    $cancel_stmt->close();
}

// Get filter parameter
$filter = isset($_GET['filter']) ? $_GET['filter'] : 'upcoming';
$today = date('Y-m-d');

// Build query based on filter
if ($filter == 'upcoming') {
    $query = "
        SELECT a.*, d.specialization 
        FROM appointments a
        JOIN doctors d ON a.doctor_id = d.doctor_id
        WHERE a.patient_id = ? AND a.appointment_date >= ? AND a.status IN ('scheduled', 'confirmed')
        ORDER BY a.appointment_date ASC, a.appointment_time ASC
    ";
    $stmt = $conn->prepare($query);
    $stmt->bind_param("is", $patient_id, $today);
} elseif ($filter == 'past') {
    $query = "
        SELECT a.*, d.specialization 
        FROM appointments a
        JOIN doctors d ON a.doctor_id = d.doctor_id
        WHERE a.patient_id = ? AND (a.appointment_date < ? OR a.status IN ('completed', 'cancelled', 'no_show'))
        ORDER BY a.appointment_date DESC, a.appointment_time DESC
    ";
    $stmt = $conn->prepare($query);
    $stmt->bind_param("is", $patient_id, $today);
} else {
    $query = "
        SELECT a.*, d.specialization 
        FROM appointments a
        JOIN doctors d ON a.doctor_id = d.doctor_id
        WHERE a.patient_id = ?
        ORDER BY a.appointment_date DESC, a.appointment_time DESC
    ";
    $stmt = $conn->prepare($query);
    $stmt->bind_param("i", $patient_id);
}

$stmt->execute();
$appointments = $stmt->get_result();
$conn->close();
?>

<!DOCTYPE html>
<html>
<head>
    <title>My Appointments - SCIS Hospital</title>
    <link rel="stylesheet" href="style.css">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            background-image: url("hospital.jpeg");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            font-family: Arial, Helvetica, sans-serif;
        }
        
        .appointments-container {
            max-width: 1200px;
            margin: 30px auto;
            background: rgba(255,255,255,0.95);
            border-radius: 10px;
            padding: 25px;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
        }
        
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid #2a7de1;
            padding-bottom: 15px;
            margin-bottom: 25px;
            flex-wrap: wrap;
        }
        
        .header h1 {
            color: #1e3a5f;
            font-size: 28px;
        }
        
        .filter-buttons {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        
        .filter-btn {
            padding: 10px 20px;
            background: #e9ecef;
            color: #333;
            text-decoration: none;
            border-radius: 5px;
            transition: all 0.3s;
        }
        
        .filter-btn.active {
            background: #2a7de1;
            color: white;
        }
        
        .filter-btn:hover {
            background: #1f5fbf;
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
            font-weight: bold;
        }
        
        .appointment-table tr:hover {
            background: #f5f5f5;
        }
        
        .status-badge {
            display: inline-block;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
        }
        
        .status-scheduled { background: #ffc107; color: #333; }
        .status-confirmed { background: #17a2b8; color: white; }
        .status-completed { background: #28a745; color: white; }
        .status-cancelled { background: #dc3545; color: white; }
        .status-no_show { background: #6c757d; color: white; }
        
        .cancel-btn {
            background: #dc3545;
            color: white;
            border: none;
            padding: 5px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
        }
        
        .cancel-btn:hover {
            background: #c82333;
        }
        
        .view-btn {
            background: #17a2b8;
            color: white;
            padding: 5px 12px;
            text-decoration: none;
            border-radius: 4px;
            font-size: 12px;
            display: inline-block;
        }
        
        .book-new-btn {
            background: #28a745;
            color: white;
            padding: 12px 25px;
            text-decoration: none;
            border-radius: 5px;
            display: inline-block;
            margin-top: 20px;
        }
        
        .book-new-btn:hover {
            background: #1e7e34;
        }
        
        .back-btn {
            background: #6c757d;
            color: white;
            padding: 10px 20px;
            text-decoration: none;
            border-radius: 5px;
            display: inline-block;
            margin-left: 10px;
        }
        
        .back-btn:hover {
            background: #5a6268;
        }
        
        .no-appointments {
            text-align: center;
            padding: 40px;
            background: #f8f9fa;
            border-radius: 8px;
            margin-top: 20px;
        }
        
        .success-msg {
            background: #d4edda;
            color: #155724;
            padding: 12px;
            border-radius: 5px;
            margin-bottom: 20px;
            border-left: 4px solid #28a745;
        }
        
        .error-msg {
            background: #f8d7da;
            color: #721c24;
            padding: 12px;
            border-radius: 5px;
            margin-bottom: 20px;
            border-left: 4px solid #dc3545;
        }
        
        .urgency-badge {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 11px;
            color: white;
        }
        
        .urgency-low { background: #28a745; }
        .urgency-medium { background: #ffc107; color: #333; }
        .urgency-high { background: #ff9800; }
        .urgency-critical { background: #dc3545; }
        
        .action-buttons {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }
        
        @media (max-width: 768px) {
            .appointments-container {
                padding: 15px;
                margin: 15px;
            }
            .appointment-table {
                font-size: 12px;
            }
            .appointment-table th, .appointment-table td {
                padding: 8px;
            }
            .filter-buttons {
                justify-content: center;
            }
        }
    </style>
</head>
<body>

<div class="appointments-container">
    <div class="header">
        <h1>📋 My Appointments</h1>
        <div>
            <a href="patient_dashboard.php" class="back-btn">← Dashboard</a>
            <a href="logout.php" class="back-btn" style="background: #dc3545;">Logout</a>
        </div>
    </div>
    
    <div class="filter-buttons">
        <a href="?filter=upcoming" class="filter-btn <?php echo $filter == 'upcoming' ? 'active' : ''; ?>">📅 Upcoming</a>
        <a href="?filter=past" class="filter-btn <?php echo $filter == 'past' ? 'active' : ''; ?>">📜 Past</a>
        <a href="?filter=all" class="filter-btn <?php echo $filter == 'all' ? 'active' : ''; ?>">📋 All</a>
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
                    <th>Doctor</th>
                    <th>Specialization</th>
                    <th>Symptoms</th>
                    <th>Urgency</th>
                    <th>Status</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                <?php while($apt = $appointments->fetch_assoc()): 
                    $urgency = isset($apt['urgency_level']) ? $apt['urgency_level'] : 'low';
                ?>
                <tr>
                    <td><?php echo date('d M Y', strtotime($apt['appointment_date'])); ?></td>
                    <td><?php echo date('g:i A', strtotime($apt['appointment_time'])); ?></td>
                    <td>Doctor ID: <?php echo $apt['doctor_id']; ?></td>
                    <td><?php echo htmlspecialchars($apt['specialization']); ?></td>
                    <td><?php echo htmlspecialchars(substr($apt['symptoms_description'], 0, 40)) ?: 'Not specified'; ?>...</td>
                    <td><span class="urgency-badge urgency-<?php echo $urgency; ?>"><?php echo ucfirst($urgency); ?></span></td>
                    <td><span class="status-badge status-<?php echo $apt['status']; ?>"><?php echo ucfirst(str_replace('_', ' ', $apt['status'])); ?></span></td>
                    <td class="action-buttons">
                        <?php if ($apt['status'] == 'scheduled' || $apt['status'] == 'confirmed'): ?>
                            <form method="POST" onsubmit="return confirm('Are you sure you want to cancel this appointment?');">
                                <input type="hidden" name="appointment_id" value="<?php echo $apt['appointment_id']; ?>">
                                <button type="submit" name="cancel_appointment" class="cancel-btn">Cancel</button>
                            </form>
                        <?php endif; ?>
                        <a href="view_appointment_details.php?id=<?php echo $apt['appointment_id']; ?>" class="view-btn">View Details</a>
                    </td>
                </tr>
                <?php endwhile; ?>
            </tbody>
        </table>
    <?php else: ?>
        <div class="no-appointments">
            <p>📭 No appointments found.</p>
            <p style="margin-top: 15px;">
                <a href="book_appointment.php" class="book-new-btn">📅 Book New Appointment</a>
            </p>
        </div>
    <?php endif; ?>
    
    <div style="margin-top: 20px; text-align: center;">
        <a href="book_appointment.php" class="book-new-btn">➕ Book New Appointment</a>
    </div>
</div>

</body>
</html>